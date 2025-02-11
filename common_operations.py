import streamlit as st

def confirm_delete(item_type, item_name):
    st.warning(f"Are you sure you want to delete the {item_type} '{item_name}'?")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Yes, delete"):
            return True
    with col2:
        if st.button("No, cancel"):
            st.rerun()
    return False


def create_list_item(name, item_type, on_delete):
    st.markdown(f'<div class="{item_type}-item"><i class="fas fa-{"book" if item_type == "subject" else "file-alt"}"></i>{name}</div>', unsafe_allow_html=True)
    if st.button("🗑️ Delete", key=f"delete_{item_type}_{name}"):
        st.session_state.delete_confirmation = (item_type, name)
        st.rerun()

