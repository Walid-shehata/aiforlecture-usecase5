import streamlit as st
from dotenv import load_dotenv
from manage_subjects import manage_subjects
from manage_chapters import manage_chapters
from upload_materials import upload_materials
from Topics_Summarizer import topicsSummary
from topicSummaryCreator import topicSummaryCreator
from Elaborate import ElaborativeOutputyCreator
from LectureAnalyzer import lecture_analyzer
from lecture_planner import lecture_planner
import base64

# Set page config to wide mode
st.set_page_config(layout="wide")

# Initialize session state variables
if 'new_subject_input' not in st.session_state:
    st.session_state.new_subject_input = ""
if 'new_chapter_input' not in st.session_state:
    st.session_state.new_chapter_input = ""
if 'delete_confirmation' not in st.session_state:
    st.session_state.delete_confirmation = None
if 'new_topics' not in st.session_state:
    st.session_state.new_topics = ""

# Load environment variables
load_dotenv()

# Add background image
def add_bg_from_local(image_file):
    with open(image_file, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode()
    st.markdown(
    f"""
    <style>
    .stApp {{
        background-image: url(data:image/png;base64,{encoded_string});
        background-size: cover;
    }}
    </style>
    """,
    unsafe_allow_html=True
    )

add_bg_from_local('bg.jpg')
st.markdown("""
<style>
    /* Main container styling */
    .main .block-container {
        max-width: 100%;
        padding-top: 1rem;
        padding-right: 1rem;
        padding-left: 1rem;
        padding-bottom: 1rem;
    }
    h1#ai-powered-content-generation-teacher-assistant
     {
        color: black;
        font-weight: bold;
        margin-bottom: 0.3rem;
    }
    h3#current-subjects,
    h3#create-new-subject,
    h3#subject-chapters,
    h3#create-new-chapter,
    h3#files-in-selected-subject-chapter,
    h3#upload-new-file,
    h3#current-topics,
    h3#topics,
    h3#video-player,
    h3#create-new-assets,
    h3#existing-assets,
    h3#generated-presentation-structure,
    h3#review-and-edit-presentation-structure
     {
        color: #fda53e;
        font-size: 1.5rem;
        font-weight: bold;
        margin-bottom: 0.3rem;
    }
    p {
        color: black;
        font-size: 4rem;
        font-weight: bold;
        line-height: 1.5;
    }
    ol, li{
        color: black;
        font-size: 1.2rem;
        line-height: 1.5;
    }
    /* Button styling */
    .stButton>button {
        background-color: #fda53e;
        color: black;
        border: none;
        border-radius: 20px;
        padding: 0.5rem 1rem;
        font-size: 2rem;
        font-weight: 900;
        transition: all 0.2s ease;
    }

    .stButton>button:hover {
        background-color: #E97527;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        transform: translateY(-5px);
    }
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 15px;
    }

    .stTabs [data-baseweb="tab"] {
        height: 40px;
        padding: 10px 16px !important;
        white-space: normal !important;
        background-color: #fda53e;
        border-radius: 5px 5px 0 0;
        color: #fda53e;
        font-weight: 500;
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
        min-width: 120px;
        border: 2px solid transparent;
    }

    .stTabs [aria-selected="true"] {
        background-color: white;
        color: black;
        font-weight: 900;
        border-color: #E97527;
        border-bottom: none;
    }
    .stTabs [aria-selected="true"]::after {
        content: '';
        position: absolute;
        bottom: -2px;
        left: 0;
        right: 0;
        height: 2px;
        background-color: white;
    }
    /* Expander styling */
    .stExpander {
        border: none;
    }
    .stExpander > details {
        background-color: #fda53e;
        border-radius: 15px;
        border: none;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        transition: all 0.3s ease;
    }
    .stExpander > details > summary {
        padding: 1rem;
        font-weight: 1000;
        color: black;
        cursor: pointer;
        font-size: 2rem;
        transition: all 0.3s ease;
    }
    .stExpander > details > summary:hover {
        background-color: #E97527;
        color: white;
    }
    .stExpander > details > summary > span {
        margin-right: 1rem;
    }
    .stExpander > details > summary > svg {
        color: black;
        transition: all 0.3s ease;
    }
    .stExpander > details[open] > summary {
        border-bottom: 1px solid rgba(0, 0, 0, 0.1);
    }
    .stExpander > details > div {
        background-color: white;
        padding: 1rem;
        border-radius: 0 0 15px 15px;
    }
    /* Additional styles for expander content */
    .streamlit-expanderContent {
        background-color: white;
        border-radius: 0 0 15px 15px;
        padding: 1rem;
    }
    .stTextInput > div[data-baseweb="input"] > div:hover,
    .stSelectbox > div[data-baseweb="select"] > div:hover {
        border-color: #fda53e;
    }
    .subject-item,
    .chapter-item {
        font-size: 1.2rem;
        color: black;
        display: flex;
        align-items: center;
        margin-bottom: 0.5rem;
        margin-right: 0.5rem;
    }

</style>
""", unsafe_allow_html=True)
def main():
    st.title("AI-Powered Content Generation Teacher-Assistant")

    # Add some padding
    st.markdown("<br>", unsafe_allow_html=True)
    tab_titles = ["Subjects Manager", "Syllabus Outliner", "Reference Materials", "Syllabus Topics", "Lessons' Summaries", "Elaborative Materials", "Lecture Analyzer", "Lecture Planner"]
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(tab_titles)

    with tab1:
        manage_subjects()
    with tab2:
        manage_chapters()
    with tab3:
        upload_materials()
    with tab4:
        topicsSummary()
    with tab5:
        topicSummaryCreator()
    with tab6:
        ElaborativeOutputyCreator()
    with tab7:
        lecture_analyzer()
    with tab8:
        lecture_planner()
    # Add some padding at the bottom
    st.markdown("<br><br>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()