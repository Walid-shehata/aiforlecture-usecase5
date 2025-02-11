import streamlit as st
import boto3
import os
import json
import sys
from dotenv import load_dotenv
from subjects import get_subjects
from chapters import get_chapters
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageTemplate, Frame, Table, HRFlowable, TableStyle


load_dotenv()

# Initialize AWS clients
s3 = boto3.client('s3',
                  aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                  aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                  region_name=os.getenv('AWS_REGION')
                  )

bedrock_runtime = boto3.client('bedrock-runtime',
                               aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                               aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                               region_name=os.getenv('AWS_REGION')
                               )

bedrock_agent_runtime = boto3.client(service_name='bedrock-agent-runtime', region_name=os.getenv('AWS_REGION'))

BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
ARIFACTS_BUCKET_NAME = os.getenv('S3_ARTIFACTS_BUCKET_NAME')
KNOWLEDGE_BASE_ID = os.getenv('BEDROCK_KNOWLEDGE_BASE_ID')


def generate_pdf(subject, chapter, topic, summary):
    buffer = io.BytesIO()

    def add_border(canvas, doc):
        canvas.setStrokeColor(colors.black)
        canvas.setLineWidth(3)
        canvas.rect(20, 20, letter[0] - 40, letter[1] - 40)

    page_template = PageTemplate(id='bordered_page',
                                 frames=[Frame(30, 30, letter[0] - 60, letter[1] - 60)],
                                 onPage=add_border)

    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=30, rightMargin=30, topMargin=30, bottomMargin=30)
    doc.addPageTemplates(page_template)

    styles = getSampleStyleSheet()

    # Modify the 'Normal' style for body text
    styles['Normal'].fontSize = 12
    styles['Normal'].leading = 14

    # Custom styles
    styles.add(ParagraphStyle(name='UniversityName', fontSize=20, textColor=colors.darkorange, spaceAfter=10))
    styles.add(ParagraphStyle(name='PoweredBy', fontSize=12, textColor=colors.black, spaceAfter=8))
    styles.add(ParagraphStyle(name='SubjectChapter', fontSize=15, textColor=colors.darkgreen, bold=True, spaceAfter=8))
    styles.add(ParagraphStyle(name='Topic', fontSize=13, textColor=colors.darkred, bold=True, spaceAfter=6))

    story = []

    # Add university name and "Powered by" paragraphs
    story.append(Paragraph("AnyUniversity", styles['UniversityName']))
    story.append(Paragraph("Powered By Amazon Bedrock", styles['PoweredBy']))

    # Add subject and chapter
    story.append(Paragraph(f"Subject Name: {subject}", styles['SubjectChapter']))
    story.append(Paragraph(f"Chapter Name: {chapter}", styles['SubjectChapter']))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.black, spaceAfter=8))

    # Add topic
    story.append(Paragraph(f"Topic Name: {topic}", styles['Topic']))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.black, spaceAfter=8))

    # Add summary using the modified 'Normal' style
    story.append(Paragraph(summary, styles['Normal']))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.black, spaceAfter=8))
    # Add logo
    logo_path = "logo.png"
    logo = Image(logo_path, width=200, height=200)
    story.append(Spacer(1, 100))  # Add some space before the logo
    story.append(Table([[logo]], colWidths=[letter[0] - 60], style=[('ALIGN', (0, 0), (-1, -1), 'RIGHT')]))

    # Build the PDF
    doc.build(story)

    buffer.seek(0)
    return buffer




def get_pdf_summary(subject, chapter, topic):
    key = f"{subject}/{chapter}/{topic}/summary.pdf"
    try:
        response = s3.get_object(Bucket=ARIFACTS_BUCKET_NAME, Key=key)
        return response['Body'].read()
    except s3.exceptions.NoSuchKey:
        return None
    except Exception as e:
        print(f"Error retrieving PDF summary: {str(e)}")
        return None

def get_presigned_url(bucket_name, object_key, expiration=3600):
    try:
        response = s3.generate_presigned_url('get_object',
                                             Params={'Bucket': bucket_name,
                                                     'Key': object_key},
                                             ExpiresIn=expiration)
        return response
    except Exception as e:
        print(f"Error generating presigned URL: {str(e)}")
        return None



def get_topics(subject, chapter):
    subject_metadata_key = f"{subject}/subject_metadata.json"
    try:
        response = s3.get_object(Bucket=BUCKET_NAME, Key=subject_metadata_key)
        subject_metadata = json.loads(response['Body'].read().decode('utf-8'))
        topics = []
        for file_info in subject_metadata.get('files', []):
            if file_info['chapter'] == chapter:
                topics.extend(file_info.get('topics', '').split('\n'))
        return [topic.strip() for topic in topics if topic.strip()]
    except s3.exceptions.NoSuchKey:
        return []

def generate_topic_summary(subject, chapter, topic):
    query = f"""Summarize the following topic:
    Subject: {subject}
    Chapter: {chapter}
    Topic: {topic}
    """
    response = bedrock_agent_runtime.retrieve(
        knowledgeBaseId=KNOWLEDGE_BASE_ID,
        retrievalQuery={'text': query},
        retrievalConfiguration={'vectorSearchConfiguration': {'numberOfResults': 6}}
    )

    context = "Based on the following information:\n\n"
    for result in response['retrievalResults']:
        if 'text' in result['content']:
            context += f"- {result['content']['text']}\n"
        elif 'byteContent' in result['content']:
            content_type = result['content']['byteContent'].split(';')[0].split(':')[1]
            context += f"- [Content of type: {content_type}]\n"

    prompt = f"""{context}
    You are a Tutor for a High-Education University.
    Provide a comprehensive Academic summary of the topic: {topic}
    Be brief. Stay Professional. Use only the provided context, don't use any extra knowledge of your own.
    Just mention the summary with no Intros, direct to the point.
    """

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
    response_body = json.loads(bedrock_response['body'].read())
    return response_body['content'][0]['text'].strip()


def save_summary(subject, chapter, topic, summary):
    text_key = f"{subject}/{chapter}/{topic}/summary.txt"
    pdf_key = f"{subject}/{chapter}/{topic}/summary.pdf"
    try:
        # Save text version
        s3.put_object(Bucket=ARIFACTS_BUCKET_NAME, Key=text_key, Body=summary.encode('utf-8'))

        # Generate and save PDF version
        pdf_buffer = generate_pdf(subject, chapter, topic, summary)
        s3.put_object(Bucket=ARIFACTS_BUCKET_NAME, Key=pdf_key, Body=pdf_buffer.getvalue())
        return True
    except Exception as e:
        return False


def get_summary(subject, chapter, topic):
    key = f"{subject}/{chapter}/{topic}/summary.txt"
    try:
        response = s3.get_object(Bucket=ARIFACTS_BUCKET_NAME, Key=key)
        return response['Body'].read().decode('utf-8')
    except s3.exceptions.NoSuchKey:
        return None
    except Exception as e:
        print(f"Error retrieving summary: {str(e)}")
        return None

def delete_summary(subject, chapter, topic):
    text_key = f"{subject}/{chapter}/{topic}/summary.txt"
    pdf_key = f"{subject}/{chapter}/{topic}/summary.pdf"
    try:
        s3.delete_object(Bucket=ARIFACTS_BUCKET_NAME, Key=text_key)
        s3.delete_object(Bucket=ARIFACTS_BUCKET_NAME, Key=pdf_key)
        print(f"Summary deleted successfully: {text_key} and {pdf_key}")
    except Exception as e:
        print(f"Error deleting summary: {str(e)}")
        raise

def topicSummaryCreator():
    with st.expander("📚 Click here for Tool Instructions"):
        st.markdown("""
        **How to use the Lessons' Summary Creator:**
        1. Select a subject from the first dropdown menu.
        2. Select a chapter from the second dropdown menu.
        3. You'll see a list of topics for the selected subject and chapter.
        4. For each topic:
           -⬤  indicates indicates an existing summary
           -◯   indicates indicates no summary available
        5. To generate a new summary:
           - Click the "Generate" button next to a topic without a summary
           - Wait for the AI to generate the summary
        6. To view or edit an existing summary:
           - Click the "View/Edit" button next to a topic with a summary
           - Edit the summary in the text area that appears
           - Click "Save Summary" to update the summary
        7. To delete a summary:
           - Click the "Delete" button next to a topic with a summary
        8. To download a PDF version of the summary:
           - Click the "Download PDF" link if available
        9. Use the "Refresh" button at the top to update the page if needed
        10. Remember to save your changes after editing a summary""")

    if 'refresh_key' not in st.session_state:
        st.session_state.refresh_key = 0
    if 'current_summary' not in st.session_state:
        st.session_state.current_summary = ""

    if st.button("Refresh"):
        st.session_state.refresh_key += 1

    subjects = [""] + get_subjects()
    subject = st.selectbox("Select Subject", subjects, key=f"subject_{st.session_state.refresh_key}")
    if subject:
        chapters = [""] + get_chapters(subject)
        chapter = st.selectbox("Select Chapter", chapters, key=f"chapter_{st.session_state.refresh_key}")
        if chapter:
            topics = get_topics(subject, chapter)
            st.subheader("Topics")

            for topic in topics:
                summary_exists = get_summary(subject, chapter, topic) is not None
                expander_label = f"⬤ {topic}" if summary_exists else f"◯ {topic}"

                with st.expander(expander_label):
                    col1, col2, col3 = st.columns([2, 1, 1])
                    pdf_key = f"{subject}/{chapter}/{topic}/summary.pdf"
                    pdf_exists = get_pdf_summary(subject, chapter, topic) is not None

                    with col1:
                        st.write("Summary status: " + ("Exists" if summary_exists else "Not available"))

                    with col2:
                        if summary_exists:
                            if st.button("View/Edit", key=f"view_{topic}_{st.session_state.refresh_key}"):
                                st.session_state.selected_topic = topic
                                st.session_state.action = "view"
                        else:
                            if st.button("Generate", key=f"generate_{topic}_{st.session_state.refresh_key}"):
                                st.session_state.selected_topic = topic
                                st.session_state.action = "generate"

                    with col3:
                        if summary_exists:
                            if st.button("Delete", key=f"delete_{topic}_{st.session_state.refresh_key}"):
                                delete_summary(subject, chapter, topic)
                                st.success(f"Summary for '{topic}' deleted successfully!")
                                st.session_state.refresh_key += 1
                                st.session_state.pop('selected_topic', None)
                                st.session_state.pop('action', None)
                                st.rerun()

                        if pdf_exists:
                            presigned_url = get_presigned_url(ARIFACTS_BUCKET_NAME, pdf_key)
                            if presigned_url:
                                st.markdown(f"[Download PDF]({presigned_url})")
                            else:
                                st.write("PDF unavailable")

            if 'selected_topic' in st.session_state:
                topic = st.session_state.selected_topic
                st.subheader(f"Summary for: {topic}")

                if st.session_state.action == "generate":
                    with st.spinner("Generating summary..."):
                        generated_summary = generate_topic_summary(subject, chapter, topic)
                        st.session_state.current_summary = generated_summary
                    st.success("Summary generated. You can now edit and save it.")
                    st.session_state.action = "view"

                if st.session_state.action == "view":
                    if not st.session_state.current_summary:
                        st.session_state.current_summary = get_summary(subject, chapter, topic) or ""

                with st.form(key=f"summary_form_{topic}"):
                    edited_summary = st.text_area(
                        "Edit summary:",
                        value=st.session_state.current_summary,
                        height=300,
                        key=f"summary_area_{topic}_{st.session_state.refresh_key}"
                    )

                    submit_button = st.form_submit_button("Save Summary")

                    if submit_button:
                        save_success = save_summary(subject, chapter, topic, edited_summary)
                        if save_success:
                            st.session_state.current_summary = edited_summary
                            st.success(f"Summary for '{topic}' saved successfully!")
                            st.session_state.refresh_key += 1
                            st.rerun()
                        else:
                            st.error("Failed to save summary. Please try again.")