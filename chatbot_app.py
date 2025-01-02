import streamlit as st
from langchain_openai import ChatOpenAI  # Updated import
import os

# Set OpenAI API Key
os.environ["OPENAI_API_KEY"] = "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"

# Initialize the chat model
chat_model = ChatOpenAI(model_name="gpt-4", temperature=0.7)

# Streamlit interface
st.title("Simple Chatbot")
st.markdown("This is a GPT-4-based chatbot. Type your question below!")

# Store chat history in session state
if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "assistant", "content": "Hello! How can I assist you today?"}]

# User input
user_input = st.text_input("You:", "", key="user_input")

# Process user input
if user_input:
    # Add the user's message
    st.session_state["messages"].append({"role": "user", "content": user_input})
    try:
        # Prepare input for the invoke method
        input_messages = st.session_state["messages"]
        
        # Debugging: Print messages being sent to the model
        st.write("Messages being sent:", input_messages)
        
        # Call OpenAI API
        response = chat_model.invoke(input=input_messages)  # Corrected argument name
        st.session_state["messages"].append({"role": "assistant", "content": response.content})
    except Exception as e:
        # Display error details for debugging
        st.session_state["messages"].append({"role": "assistant", "content": "An error occurred. Please try again."})
        st.error(f"Error details: {str(e)}")

# Display chat history
for msg in st.session_state["messages"]:
    if msg["role"] == "user":
        st.markdown(f"**You:** {msg['content']}")
    else:
        st.markdown(f"**Chatbot:** {msg['content']}")
