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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Image, PageTemplate, Frame, Table, HRFlowable
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, FrameBreak, NextPageTemplate, Spacer



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

    def add_border_and_logo(canvas, doc):
        canvas.saveState()
        # Add border
        canvas.setStrokeColor(colors.black)
        canvas.setLineWidth(3)
        canvas.rect(20, 20, letter[0] - 40, letter[1] - 40)

        # Add logo
        logo_path = "logo.png"
        logo_width = 1.5 * inch
        logo_height = 1.5 * inch
        canvas.drawImage(logo_path, letter[0] - logo_width - 0.5 * inch, 0.5 * inch, width=logo_width,
                         height=logo_height)

        canvas.restoreState()

    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=30, rightMargin=30, topMargin=30, bottomMargin=30)

    styles = getSampleStyleSheet()

    # Modify the 'Normal' style for body text
    styles['Normal'].fontSize = 12
    styles['Normal'].leading = 14
    styles['Normal'].spaceAfter = 10  # Add space after each paragraph

    # Custom styles
    styles.add(ParagraphStyle(name='UniversityName', fontSize=20, textColor=colors.darkorange, spaceAfter=10))
    styles.add(ParagraphStyle(name='PoweredBy', fontSize=12, textColor=colors.black, spaceAfter=20))
    styles.add(ParagraphStyle(name='SubjectChapter', fontSize=15, textColor=colors.darkgreen, bold=True, spaceAfter=8))
    styles.add(ParagraphStyle(name='Topic', fontSize=13, textColor=colors.darkred, bold=True, spaceAfter=15))

    story = []

    # Add university name and "Powered by" paragraphs
    story.append(Paragraph("AnyUniversity", styles['UniversityName']))
    story.append(Paragraph("Powered By Amazon Bedrock", styles['PoweredBy']))

    # Add subject and chapter
    story.append(Paragraph(f"Subject Name: {subject}", styles['SubjectChapter']))
    story.append(Paragraph(f"Chapter Name: {chapter}", styles['SubjectChapter']))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.black, spaceAfter=15))

    # Add topic
    story.append(Paragraph(f"Topic Name: {topic}", styles['Topic']))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.black, spaceAfter=15))

    # Split the summary into paragraphs and add them individually
    paragraphs = summary.split('\n\n')
    for para in paragraphs:
        story.append(Paragraph(para.strip(), styles['Normal']))

    story.append(HRFlowable(width="100%", thickness=2, color=colors.black, spaceAfter=15))

    # Add space at the bottom of each page for the logo
    story.append(Spacer(1, 2 * inch))

    # Build the PDF
    doc.build(story, onFirstPage=add_border_and_logo, onLaterPages=add_border_and_logo)

    buffer.seek(0)
    return buffer



def get_pdf_summary(subject, chapter, topic):
    key = f"{subject}/{chapter}/{topic}/Elaborate.pdf"
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
    query = f"""For the following:
    Subject: {subject}
    Chapter: {chapter}
    Topic: {topic}
    Retrieve the relative Information
    """
    response = bedrock_agent_runtime.retrieve(
        knowledgeBaseId=KNOWLEDGE_BASE_ID,
        retrievalQuery={'text': query},
        retrievalConfiguration={'vectorSearchConfiguration': {'numberOfResults': 10}}
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
    Your students are facing issues in understanding the following " {topic} " from the previous context.
    Use your knowledge to explain and simplify the mentioned topics. Give examples and Elaborate.
    """

    bedrock_response = bedrock_runtime.invoke_model(
        modelId="anthropic.claude-3-sonnet-20240229-v1:0",
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "top_p": 1.0,
        })
    )
    response_body = json.loads(bedrock_response['body'].read())
    return response_body['content'][0]['text'].strip()


def save_summary(subject, chapter, topic, summary):
    text_key = f"{subject}/{chapter}/{topic}/Elaborate.txt"
    pdf_key = f"{subject}/{chapter}/{topic}/Elaborate.pdf"
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
    key = f"{subject}/{chapter}/{topic}/Elaborate.txt"
    try:
        response = s3.get_object(Bucket=ARIFACTS_BUCKET_NAME, Key=key)
        return response['Body'].read().decode('utf-8')
    except s3.exceptions.NoSuchKey:
        return None
    except Exception as e:
        print(f"Error retrieving summary: {str(e)}")
        return None

def delete_summary(subject, chapter, topic):
    text_key = f"{subject}/{chapter}/{topic}/Elaborate.txt"
    pdf_key = f"{subject}/{chapter}/{topic}/Elaborate.pdf"
    try:
        s3.delete_object(Bucket=ARIFACTS_BUCKET_NAME, Key=text_key)
        s3.delete_object(Bucket=ARIFACTS_BUCKET_NAME, Key=pdf_key)
        print(f"Summary deleted successfully: {text_key} and {pdf_key}")
    except Exception as e:
        print(f"Error deleting summary: {str(e)}")
        raise

def ElaborativeOutputyCreator():
    with st.expander("📚 Click here for Tool Instructions"):
        st.markdown("""
        **How to use the Elaborative-Materials Creator:**
        1. Select a subject from the first dropdown menu.
        2. Select a chapter from the second dropdown menu.
        3. You'll see a list of topics for the selected subject and chapter.
        4. For each topic:
           -⬤  indicates an existing elaborative explanation
           -◯   indicates no elaborative explanation available
        5. To generate a new elaborative explanation:
           - Click the "Generate" button next to a topic without an explanation
           - Wait for the AI to generate the detailed explanation with examples
        6. To view or edit an existing explanation:
           - Click the "View/Edit" button next to a topic with an explanation
           - Edit the explanation in the text area that appears
           - Click "Save Explanation" to update the content
        7. To delete an explanation:
           - Click the "Delete" button next to a topic with an explanation
        8. To download a PDF version of the elaborative explanation:
           - Click the "Download PDF" link if available
        9. Use the "Refresh" button at the top to update the page if needed
        10. Remember to save your changes after editing an explanation
        11. This tool provides more detailed explanations and examples to help understand complex topics better.
        """)
    if 'refresh_key2' not in st.session_state:
        st.session_state.refresh_key = 0
    if 'current_summary' not in st.session_state:
        st.session_state.current_summary = ""

    if st.button("Refresh", key="Refresh2"):
        st.session_state.refresh_key += 1

    subjects = [""] + get_subjects()
    subject = st.selectbox("Select Subject", subjects, key=f"subject2_{st.session_state.refresh_key}")
    if subject:
        chapters = [""] + get_chapters(subject)
        chapter = st.selectbox("Select Chapter", chapters, key=f"chapter2_{st.session_state.refresh_key}")
        if chapter:
            topics = get_topics(subject, chapter)
            st.subheader("Topics")

            for topic in topics:
                summary_exists = get_summary(subject, chapter, topic) is not None
                expander_label = f"⬤ {topic}" if summary_exists else f"◯ {topic}"

                with st.expander(expander_label):
                    col1, col2, col3 = st.columns([2, 1, 1])
                    pdf_key = f"{subject}/{chapter}/{topic}/Elaborate.pdf"
                    pdf_exists = get_pdf_summary(subject, chapter, topic) is not None

                    with col1:
                        st.write("Extra Explanation status: " + ("Exists" if summary_exists else "Not available"))

                    with col2:
                        if summary_exists:
                            if st.button("View/Edit", key=f"view2_{topic}_{st.session_state.refresh_key}"):
                                st.session_state.selected_topic = topic
                                st.session_state.action = "view"
                        else:
                            if st.button("Generate", key=f"generate2_{topic}_{st.session_state.refresh_key}"):
                                st.session_state.selected_topic = topic
                                st.session_state.action = "generate"

                    with col3:
                        if summary_exists:
                            if st.button("Delete", key=f"delete2_{topic}_{st.session_state.refresh_key}"):
                                delete_summary(subject, chapter, topic)
                                st.success(f"Extra Explanation for '{topic}' deleted successfully!")
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
                st.subheader(f"Extra Explanation for: {topic}")

                if st.session_state.action == "generate":
                    with st.spinner("Generating more explanation and examples ..."):
                        generated_summary = generate_topic_summary(subject, chapter, topic)
                        st.session_state.current_summary = generated_summary
                    st.success("Elaborative Output has been generated. You can now edit and save it.")
                    st.session_state.action = "view"

                if st.session_state.action == "view":
                    if not st.session_state.current_summary:
                        st.session_state.current_summary = get_summary(subject, chapter, topic) or ""

                with st.form(key=f"summary2_form_{topic}"):
                    edited_summary = st.text_area(
                        "Edit Explanation:",
                        value=st.session_state.current_summary,
                        height=300,
                        key=f"summary2_area_{topic}_{st.session_state.refresh_key}"
                    )

                    submit_button = st.form_submit_button("Save Explanation")

                    if submit_button:
                        save_success = save_summary(subject, chapter, topic, edited_summary)
                        if save_success:
                            st.session_state.current_summary = edited_summary
                            st.success(f"Elaborative Output for '{topic}' saved successfully!")
                            st.session_state.refresh_key += 1
                            st.rerun()
                        else:
                            st.error("Failed to save output. Please try again.")