import streamlit as st
import boto3
import os
from dotenv import load_dotenv
from common_operations import confirm_delete, create_list_item
from subjects import get_subjects
from chapters import get_chapters
from files import get_files, delete_file, display_file_list, update_subject_metadata
import json
import logging
from uuid import uuid4
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()
# Initialize AWS clients
s3 = boto3.client('s3',
                  aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                  aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                  region_name=os.getenv('AWS_REGION')
                  )
bedrock_agent = boto3.client('bedrock-agent',
                                     aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                                     aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                                     region_name=os.getenv('AWS_REGION')
                                     )

# S3 bucket name
BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
# Bedrock Knowledge Base ID
KNOWLEDGE_BASE_ID = os.getenv('BEDROCK_KNOWLEDGE_BASE_ID')
# Bedrock Data Source ID
DATA_SOURCE_ID = os.getenv('BEDROCK_DATA_SOURCE_ID')


def create_update_metadata(subject, chapter, filename):
    # Create metadata for the file
    current_date = datetime.now().strftime("%Y%m%d")
    file_metadata = {
        "metadataAttributes": {
            "subject": {
                "value": {
                    "type": "STRING",
                    "stringValue": subject
                },
                "includeForEmbedding": True
            },
            "chapter": {
                "value": {
                    "type": "STRING",
                    "stringValue": chapter
                },
                "includeForEmbedding": True
            },
            "filename": {
                "value": {
                    "type": "STRING",
                    "stringValue": filename
                },
                "includeForEmbedding": True
            },
            "created_date": {
                "value": {
                    "type": "NUMBER",
                    "numberValue": int(current_date)
                },
                "includeForEmbedding": True
            }
        }
    }

    # Convert the metadata to a JSON string
    metadata_json = json.dumps(file_metadata, ensure_ascii=False, indent=2)

    # Upload file metadata
    metadata_key = f"{subject}/{chapter}/{filename}.metadata.json"
    s3.put_object(Bucket=BUCKET_NAME, Key=metadata_key, Body=metadata_json, ContentType='application/json')

    logger.info(f"Metadata created for {filename}: {metadata_json}")

    # Update subject-level metadata
    update_subject_metadata(subject, chapter, filename, action='add')

    # Verify the uploaded metadata
    if verify_metadata_json(subject, chapter, filename):
        logger.info(f"Metadata for {filename} verified successfully")
    else:
        logger.error(f"Failed to verify metadata for {filename}")


def verify_metadata_json(subject, chapter, filename):
    metadata_key = f"{subject}/{chapter}/{filename}.metadata.json"
    try:
        response = s3.get_object(Bucket=BUCKET_NAME, Key=metadata_key)
        metadata_content = response['Body'].read().decode('utf-8')
        json.loads(metadata_content)  # This will raise an exception if the JSON is invalid
        logger.info(f"Metadata for {filename} is valid JSON")
        return True
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in metadata for {filename}: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Error verifying metadata for {filename}: {str(e)}")
        return False



def sync_knowledge_base():
    logger.info(f"Attempting to sync Knowledge Base. Knowledge Base ID: {KNOWLEDGE_BASE_ID}, Data Source ID: {DATA_SOURCE_ID}")
    try:
        response = bedrock_agent.start_ingestion_job(
            knowledgeBaseId=KNOWLEDGE_BASE_ID,
            dataSourceId=DATA_SOURCE_ID
        )
        logger.info(f"Knowledge Base sync started successfully. Response: {response}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")


def upload_materials():
    with st.expander("📚 Click here for Tool Instructions"):
        st.markdown("""
        **How to use the Reference-Materials tool:**
        1. Select a subject from the first dropdown menu.
        2. Select a chapter from the second dropdown menu.
        3. View existing files for the selected subject and chapter.
        4. To delete a file, click the "Delete" button next to it and confirm your action.
        5. To upload a new file:
           - Click on "Choose a file to upload" or drag and drop a file into the designated area.
           - Once a file is selected, click the "Upload File" button to upload it.
        6. You can switch between subjects and chapters to manage files in different locations.
        """)
    subjects = [""] + get_subjects()
    selected_subject = st.selectbox("Select a subject:", subjects, key="upload_materials_subject")
    if selected_subject:
        chapters = [""] + get_chapters(selected_subject)  # Add an empty option at the beginning
        selected_chapter = st.selectbox("Select a chapter:", chapters, key="upload_materials_chapter")
        if selected_chapter:
            files = get_files(selected_subject, selected_chapter)
            display_file_list(selected_subject, selected_chapter, files)

            st.subheader("Upload New File")
            uploaded_file = st.file_uploader("Choose a file to upload", key=f"uploader_{selected_subject}_{selected_chapter}")
            if uploaded_file is not None:
                if st.button("Upload File"):
                    # Upload file to S3
                    s3_key = f"{selected_subject}/{selected_chapter}/{uploaded_file.name}"
                    s3.upload_fileobj(uploaded_file, BUCKET_NAME, s3_key)
                    # Create and update metadata
                    create_update_metadata(selected_subject, selected_chapter, uploaded_file.name)
                    st.success(f"File uploaded successfully to S3: {s3_key}")
                    # Sync Knowledge Base
                    sync_knowledge_base()
                    st.rerun()

