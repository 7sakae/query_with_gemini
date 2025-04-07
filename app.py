import streamlit as st
import pandas as pd
import datetime
import google.generativeai as genai

# --- Layout ---
st.title("🧠 CSV Chatbot with Schema Awareness")
st.subheader("Upload your data and ask questions naturally!")

# --- Gemini Setup ---
try:
    gemini_api_key = st.secrets["gemini_api_key"]
    genai.configure(api_key=gemini_api_key)
    model = genai.GenerativeModel("gemini-2.0-flash-lite")
    st.success("✅ Gemini model initialized.")
except Exception as e:
    st.error(f"❌ Failed to initialize Gemini: {e}")
    model = None

# --- Session State ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "transaction_data" not in st.session_state:
    st.session_state.transaction_data = None
if "data_dictionary" not in st.session_state:
    st.session_state.data_dictionary = None

# --- Upload Section ---
st.subheader("📁 Upload Your Files")
col1, col2 = st.columns(2)
with col1:
    transaction_file = st.file_uploader("Transaction CSV", type=["csv"], key="transactions")
with col2:
    dict_file = st.file_uploader("Data Dictionary CSV", type=["csv"], key="data_dict")

if transaction_file:
    try:
        df = pd.read_csv(transaction_file)
        st.session_state.transaction_data = df
        st.write("✅ Transaction Data Preview")
        st.dataframe(df.head())
    except Exception as e:
        st.error(f"❌ Could not load transaction file: {e}")

if dict_file:
    try:
        data_dict_df = pd.read_csv(dict_file)
        st.session_state.data_dictionary = data_dict_df
        st.write("✅ Data Dictionary Preview")
        st.dataframe(data_dict_df)
    except Exception as e:
        st.error(f"❌ Could not load data dictionary file: {e}")

# --- Chatbot Section ---
if model and st.session_state.transaction_data is not None and st.session_state.data_dictionary is not None:
    user_input = st.chat_input("Ask a question about your data...")

    if user_input:
        st.chat_message("user").markdown(user_input)

        df = st.session_state.transaction_data.copy()
        df_name = "df"
        data_dict_text = st.session_state.data_dictionary.to_string(index=False)
        example_record = df.head(2).to_string(index=False)

        # --- Code Prompt ---
        code_prompt = f"""
You are a helpful Python code generator.

Your job is to write Python code that answers the user's question using the DataFrame provided.

**User Question:**
{user_input}

**DataFrame Name:**  
{df_name}

**Data Dictionary (Column Descriptions):**  
{data_dict_text}

**Example Data (Top 2 Rows):**  
{example_record}

**Instructions:**
1. Write Python code that answers the user's question.
2. Assume the DataFrame is already loaded as `{df_name}`.
3. Use `pd.to_datetime()` for date parsing if needed.
4. Do NOT include import statements or comments.
5. Store the final output in a variable named `ANSWER`. This variable must be previously defined — do not rename or abbreviate it.
6. Return your output as pure Python code inside a single code block. Do not return markdown, headers, or plain text.
7. If the answer cannot be computed, set `ANSWER = "Unable to compute result."`
"""

        try:
            # Get and clean code
            response = model.generate_content(code_prompt)
            generated_code = response.text.strip()
            if generated_code.startswith("```"):
                generated_code = generated_code.strip("` \npython").strip("` \n")
            clean_code = "\n".join(
                line for line in generated_code.splitlines()
                if not line.strip().lower().startswith("import")
                and not line.strip().lower().startswith("from ")
            ).strip()

            # Show code
            with st.expander("📜 Show generated code"):
                st.code(clean_code, language="python")

            # Execute the code
            local_vars = {"df": df, "pd": pd, "datetime": datetime}
            exec(clean_code, {}, local_vars)
            ANSWER = local_vars.get("ANSWER", "No result returned.")

            # --- Explanation Prompt ---
            explanation_prompt = f"""
You are a data assistant. Here's a user question and the result of a Python query.
Explain the answer clearly and concisely in friendly language.

**User Question:**  
{user_input}

**Raw Result:**  
{ANSWER}

**Friendly Answer:**
"""

            human_response = model.generate_content(explanation_prompt)
            explanation = human_response.text.strip()

            # Show final explanation
            st.chat_message("assistant").markdown(f"**Explanation:**\n\n{explanation}")
            st.session_state.chat_history.append({
                "question": user_input,
                "code": clean_code,
                "raw_answer": ANSWER,
                "explanation": explanation
            })

        except Exception as e:
            st.error(f"❌ Error while generating or executing code: {e}")
else:
    st.info("📌 Upload both the transaction file and data dictionary to get started.")

# --- Show Chat History ---
if st.session_state.chat_history:
    st.markdown("## 🕓 Chat History")
    for entry in st.session_state.chat_history:
        st.markdown(f"**🧑‍💻 Question:** {entry['question']}")
        st.markdown(f"**🤖 Explanation:** {entry['explanation']}")
        with st.expander("🔍 Raw Result & Code"):
            st.write("**Raw Result:**")
            st.write(entry["raw_answer"])
            st.code(entry["code"], language="python")
