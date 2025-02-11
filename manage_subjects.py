import streamlit as st
import boto3
import os
from dotenv import load_dotenv
from common_operations import confirm_delete, create_list_item
from subjects import get_subjects, delete_subject, create_subject
import json
from uuid import uuid4
load_dotenv()
# Initialize AWS clients
s3 = boto3.client('s3',
                  aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                  aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                  region_name=os.getenv('AWS_REGION')
                  )
# S3 bucket name
BUCKET_NAME = os.getenv('S3_BUCKET_NAME')



def manage_subjects():
    with st.expander("📚 Click here for Tool Instructions"):
        st.markdown("""
        **How to use the Subjects-Manager:**
        1. View existing subjects in the "Current Subjects" section.
        2. To delete a subject, click the "Delete" button next to it and confirm your action.
        3. To create a new subject, enter the subject name in the "Create New Subject" section and click "Create Subject".
        """)
    subjects = get_subjects()

    st.subheader("Current Subjects")
    if not subjects:
        st.info("No subjects found. Create a new subject to get started.")
    else:
        for subject in subjects:
            create_list_item(subject, "subject", delete_subject)

    if st.session_state.delete_confirmation and st.session_state.delete_confirmation[0] == "subject":
        subject_to_delete = st.session_state.delete_confirmation[1]
        st.warning(f"Are you sure you want to delete the subject '{subject_to_delete}'?")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Yes, delete", key=f"confirm_delete_subject_{subject_to_delete}"):
                delete_subject(subject_to_delete)
                st.session_state.delete_confirmation = None
                st.rerun()
        with col2:
            if st.button("No, cancel", key=f"cancel_delete_subject_{subject_to_delete}"):
                st.session_state.delete_confirmation = None
                st.rerun()

    st.subheader("Create New Subject")
    new_subject = st.text_input("Enter new subject name:", key="new_subject_input")
    if st.button("Create Subject"):
        if new_subject and new_subject not in subjects:
            create_subject(new_subject)
            st.success(f"Subject '{new_subject}' created successfully.")
            st.rerun()
        else:
            st.error("Invalid subject name or subject already exists.")
