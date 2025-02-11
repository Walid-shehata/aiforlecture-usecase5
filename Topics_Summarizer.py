import streamlit as st
import boto3
import os
from dotenv import load_dotenv
from subjects import get_subjects
from chapters import get_chapters
from files import get_files, update_subject_metadata
import json
from uuid import uuid4
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

if 'new_topics' not in st.session_state:
    st.session_state.new_topics = ""

# Initialize AWS clients
s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION')
)

bedrock_runtime = boto3.client(
    'bedrock-runtime',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION')
)

bedrock_agent_runtime = boto3.client(
    service_name='bedrock-agent-runtime',
    region_name=os.getenv('AWS_REGION')
)

BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
KNOWLEDGE_BASE_ID = os.getenv('BEDROCK_KNOWLEDGE_BASE_ID')

def generate_topics(subject, chapter, filename):
    logger.info(f"Generating topics for {subject} - {chapter} - {filename}")
    query = f"""Generate a bulleted list of the main topics covered in the document:
    Subject: {subject}
    Chapter: {chapter}
    Filename: {filename}
    """
    try:
        response = bedrock_agent_runtime.retrieve(
            knowledgeBaseId=KNOWLEDGE_BASE_ID,
            retrievalQuery={'text': query},
            retrievalConfiguration={'vectorSearchConfiguration': {'numberOfResults': 5}}
        )
        logger.info("Successfully retrieved from knowledge base")
    except Exception as e:
        logger.error(f"Error retrieving from knowledge base: {str(e)}")
        return None

    context = "Based on the following information:\n\n"
    for result in response['retrievalResults']:
        if 'text' in result['content']:
            context += f"- {result['content']['text']}\n"
        elif 'byteContent' in result['content']:
            content_type = result['content']['byteContent'].split(';')[0].split(':')[1]
            context += f"- [Content of type: {content_type}]\n"

    prompt = f"""{context}
    Return a bulleted list of the main topics covered in this context.
    """

    try:
        bedrock_response = bedrock_runtime.invoke_model(
            modelId="anthropic.claude-3-sonnet-20240229-v1:0",
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "top_p": 1.0,
            })
        )
        logger.info("Successfully invoked Bedrock model")
        response_body = json.loads(bedrock_response['body'].read())
        return response_body['content'][0]['text'].strip()
    except Exception as e:
        logger.error(f"Error invoking Bedrock model: {str(e)}")
        return None

def topicsSummary():
    with st.expander("📚 Click here for Tool Instructions"):
        st.markdown("""
        **How to use the Syllabus-Topics tool:**
        1. Select a subject from the first dropdown menu.
        2. Select a chapter from the second dropdown menu.
        3. Select a document from the third dropdown menu.
        4. View and edit the current topics for the selected document in the text area.
        5. To save changes:
           - Edit the topics in the text area.
           - Click the "Save Topics" button to update the topics for the document.
        6. To generate new topics:
           - Click the "Generate New Topics" button.
           - The AI will analyze the document and suggest new topics.
           - Review and edit the generated topics as needed.
           - Click "Save Topics" to keep the new or edited topics.
        7. You can switch between different subjects, chapters, and documents to manage topics for various materials.
        8. The topics are used to summarize the main points of each document and improve searchability.
        """)
    logger.info("Starting Topics Manager")

    TOPICS_KEY = "topics_manager_current_topics"

    if TOPICS_KEY not in st.session_state:
        st.session_state[TOPICS_KEY] = ""

    subjects = [""] + get_subjects()
    subject = st.selectbox("Select Subject", subjects, key="topicsSummarySubjectSelection")

    if subject:
        logger.info(f"Selected subject: {subject}")
        chapters = [""] + get_chapters(subject)
        chapter = st.selectbox("Select Chapter", chapters, key="topicsSummaryChapterSelection")

        if chapter:
            logger.info(f"Selected chapter: {chapter}")
            files = [""] + get_files(subject, chapter)
            file = st.selectbox("Select Document", files, key="topicsSummaryfilesSelection")

            if file:
                logger.info(f"Selected file: {file}")

                subject_metadata_key = f"{subject}/subject_metadata.json"
                try:
                    response = s3.get_object(Bucket=BUCKET_NAME, Key=subject_metadata_key)
                    subject_metadata = json.loads(response['Body'].read().decode('utf-8'))

                    file_info = next(
                        (item for item in subject_metadata.get('files', [])
                         if item['filename'] == file and item['chapter'] == chapter),
                        None
                    )

                    if file_info:
                        st.session_state[TOPICS_KEY] = file_info.get('topics', '')
                    else:
                        st.session_state[TOPICS_KEY] = ''

                    logger.info("Successfully loaded topics from S3 for this file")
                except s3.exceptions.NoSuchKey:
                    logger.info("No saved topics found for this file")
                    st.session_state[TOPICS_KEY] = ''
                except Exception as e:
                    logger.error(f"Error loading saved topics: {str(e)}")
                    st.session_state[TOPICS_KEY] = ''

                st.subheader("Current Topics:")
                current_topics = st.text_area(
                    "Edit topics here:",
                    value=st.session_state.new_topics if st.session_state.new_topics else st.session_state[TOPICS_KEY],
                    height=300,
                    key="topics_text_area"
                )
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Save Topics"):
                        try:
                            update_subject_metadata(subject, chapter, file,
                                                    action='update', topics=current_topics)
                            st.session_state[TOPICS_KEY] = current_topics
                            st.session_state.new_topics = ""
                            st.success("Topics saved successfully!")
                            logger.info("Topics saved successfully")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to save topics: {str(e)}")
                            logger.error(f"Error saving topics: {str(e)}")

                with col2:
                    if st.button("Generate New Topics"):
                        logger.info("Generating new topics")
                        try:
                            new_topics = generate_topics(subject, chapter, file)
                            if new_topics:
                                st.session_state.new_topics = new_topics
                                st.success("New topics generated successfully.")
                                logger.info("New topics generated successfully")
                                st.rerun()
                            else:
                                st.warning("No new topics were generated.")
                        except Exception as e:
                            st.error(f"Failed to generate new topics: {str(e)}")
                            logger.error(f"Failed to generate new topics: {str(e)}")

    logger.info("Topics Manager completed")