import streamlit as st
import boto3
import os
from dotenv import load_dotenv
import json
from uuid import uuid4
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



def get_chapters(subject):
    response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=f"{subject}/", Delimiter='/')
    return [prefix['Prefix'].split('/')[-2] for prefix in response.get('CommonPrefixes', [])]



def create_chapter(subject_name, chapter_name):
    s3.put_object(Bucket=BUCKET_NAME, Key=f"{subject_name}/{chapter_name}/")
    st.success(f"Chapter '{chapter_name}' created successfully in subject '{subject_name}'.")
    st.rerun()

def delete_chapter(subject_name, chapter_name):
    # List all objects in the chapter folder
    objects_to_delete = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=f"{subject_name}/{chapter_name}/")
    # Delete all objects in the chapter folder
    for obj in objects_to_delete.get('Contents', []):
        s3.delete_object(Bucket=BUCKET_NAME, Key=obj['Key'])
    # Delete the chapter folder itself
    s3.delete_object(Bucket=BUCKET_NAME, Key=f"{subject_name}/{chapter_name}/")
    st.success(f"Chapter '{chapter_name}' and all its contents deleted successfully from subject '{subject_name}'.")
    # Trigger a sync after deletion
    sync_knowledge_base()


def sync_knowledge_base():
    try:
        response = bedrock_agent.start_ingestion_job(
            knowledgeBaseId=KNOWLEDGE_BASE_ID,
            dataSourceId=DATA_SOURCE_ID
        )
        st.info(f"Knowledge Base sync started. Job ID: {response['ingestionJob']['ingestionJobId']}")
    except Exception as e:
        st.error(f"Failed to start Knowledge Base sync: {str(e)}")
