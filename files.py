import streamlit as st
import boto3
import os
from dotenv import load_dotenv
import json
from uuid import uuid4
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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


def sync_knowledge_base():
    logger.info(
        f"Attempting to sync Knowledge Base. Knowledge Base ID: {KNOWLEDGE_BASE_ID}, Data Source ID: {DATA_SOURCE_ID}")
    try:
        response = bedrock_agent.start_ingestion_job(
            knowledgeBaseId=KNOWLEDGE_BASE_ID,
            dataSourceId=DATA_SOURCE_ID
        )
        logger.info(f"Knowledge Base sync started successfully. Response: {response}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during sync: {str(e)}")



def get_files(subject, chapter):
    prefix = f"{subject}/{chapter}/"
    response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
    return [obj['Key'].split('/')[-1] for obj in response.get('Contents', [])
            if obj['Key'] != prefix and not obj['Key'].endswith('.metadata.json')]


def update_subject_metadata(subject, chapter, filename, action='delete', topics=None):
    subject_metadata_key = f"{subject}/subject_metadata.json"
    try:
        response = s3.get_object(Bucket=BUCKET_NAME, Key=subject_metadata_key)
        subject_metadata = json.loads(response['Body'].read().decode('utf-8'))
    except s3.exceptions.NoSuchKey:
        subject_metadata = {"files": []}

    if action == 'delete':
        subject_metadata['files'] = [
            file for file in subject_metadata['files']
            if not (file['filename'] == filename and file['chapter'] == chapter)
        ]
    elif action == 'add':
        if not any(file['filename'] == filename and file['chapter'] == chapter
                   for file in subject_metadata['files']):
            subject_metadata['files'].append({
                "filename": filename,
                "chapter": chapter,
                "topics": []
            })
    elif action == 'update':
        for file in subject_metadata['files']:
            if file['filename'] == filename and file['chapter'] == chapter:
                file['topics'] = topics
                break
        else:
            subject_metadata['files'].append({
                "filename": filename,
                "chapter": chapter,
                "topics": topics
            })

    # Convert the metadata to a JSON string
    metadata_json = json.dumps(subject_metadata, ensure_ascii=False, indent=2)

    # Upload updated subject metadata
    s3.put_object(Bucket=BUCKET_NAME, Key=subject_metadata_key, Body=metadata_json, ContentType='application/json')




def delete_file(subject, chapter, filename):
    key = f"{subject}/{chapter}/{filename}"
    s3.delete_object(Bucket=BUCKET_NAME, Key=key)
    # Also delete the metadata file if it exists
    metadata_key = f"{subject}/{chapter}/{filename}.metadata.json"
    s3.delete_object(Bucket=BUCKET_NAME, Key=metadata_key)
    # Update subject metadata
    update_subject_metadata(subject, chapter, filename, action='delete')
    st.success(f"File '{filename}' deleted successfully.")
    sync_knowledge_base()


def display_file_list(subject, chapter, files):
    st.subheader(f"Files in selected Subject & Chapter")
    if not files:
        st.info("No files found in this chapter.")
    else:
        for file in files:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(file)
            with col2:
                download_link = s3.generate_presigned_url('get_object',
                                                          Params={'Bucket': BUCKET_NAME,
                                                                  'Key': f"{subject}/{chapter}/{file}"},
                                                          ExpiresIn=3600)
                st.markdown(f"[Download]({download_link})")
            with col3:
                if st.button("Delete", key=f"delete_file_{subject}_{chapter}_{file}"):
                    st.session_state.delete_confirmation = ("file", (subject, chapter, file))
                    st.rerun()

    if st.session_state.delete_confirmation and st.session_state.delete_confirmation[0] == "file":
        file_to_delete = st.session_state.delete_confirmation[1]
        st.warning(f"Are you sure you want to delete the file '{file_to_delete[2]}'?")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Yes, delete", key=f"confirm_delete_file_{file_to_delete[2]}"):
                delete_file(*file_to_delete)
                st.session_state.delete_confirmation = None
                st.rerun()
        with col2:
            if st.button("No, cancel", key=f"cancel_delete_file_{file_to_delete[2]}"):
                st.session_state.delete_confirmation = None
                st.rerun()
