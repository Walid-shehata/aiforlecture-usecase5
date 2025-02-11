import streamlit as st
import boto3
import os
from dotenv import load_dotenv
from common_operations import confirm_delete, create_list_item
from subjects import get_subjects
from chapters import get_chapters, delete_chapter, create_chapter
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



def manage_chapters():
    with st.expander("📚 Click here for Tool Instructions"):
        st.markdown("""
        **How to use the Syllabus-Outliner:**
        1. Select a subject from the dropdown menu.
        2. View existing chapters for the selected subject in the "Chapters in [Subject]" section.
        3. To delete a chapter, click the "Delete" button next to it and confirm your action.
        4. To create a new chapter, enter the chapter name in the "Create New Chapter" section and click "Create Chapter".
        5. You can switch between subjects to manage chapters for different subjects.
        """)
    subjects = get_subjects()
    subjects = [""] + subjects
    selected_subject = st.selectbox("Select a subject:", subjects, key="manage_chapters_subject")

    if selected_subject:
        chapters = get_chapters(selected_subject)

        st.subheader(f"Subject Chapters")
        if not chapters:
            st.info("No chapters found. Create a new chapter to get started.")
        else:
            for chapter in chapters:
                create_list_item(chapter, "chapter", lambda x=chapter: delete_chapter(selected_subject, x))

        if st.session_state.delete_confirmation and st.session_state.delete_confirmation[0] == "chapter":
            chapter_to_delete = st.session_state.delete_confirmation[1]
            st.warning(f"Are you sure you want to delete the chapter '{chapter_to_delete}'?")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Yes, delete", key=f"confirm_delete_chapter_{selected_subject}_{chapter_to_delete}"):
                    delete_chapter(selected_subject, chapter_to_delete)
                    st.session_state.delete_confirmation = None
                    st.rerun()
            with col2:
                if st.button("No, cancel", key=f"cancel_delete_chapter_{selected_subject}_{chapter_to_delete}"):
                    st.session_state.delete_confirmation = None
                    st.rerun()

        st.subheader("Create New Chapter")
        new_chapter = st.text_input("Enter new chapter name:", key=f"new_chapter_input_{selected_subject}")
        if st.button("Create Chapter", key=f"create_chapter_button_{selected_subject}"):
            if new_chapter and new_chapter not in chapters:
                create_chapter(selected_subject, new_chapter)
                st.success(f"Chapter '{new_chapter}' created successfully in subject '{selected_subject}'.")
                st.rerun()
            else:
                st.error("Invalid chapter name or chapter already exists.")

