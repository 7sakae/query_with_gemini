import streamlit as st
import pandas as pd
import datetime
import google.generativeai as genai

# --- Layout ---
st.title("🧠 CSV Chatbot with Schema Awareness")
st.subheader("Upload your data and ask questions naturally!")

# --- API Key from Secret ---
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

# --- Upload Files ---
st.subheader("📁 Upload Your Files")

col1, col2 = st.columns(2)
with col1:
    transaction_file = st.file_uploader("Transaction CSV", type=["csv"], key="transactions")
with col2:
    dict_file = st.file_uploader("Data Dictionary CSV", type=["csv"], key="data_dict")

# --- Load Files ---
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

        # --- Prompt to generate code ---
        code_prompt = f"""
You are a helpful Python code generator.

Your job is to write Python code that answers the user's question using the DataFrame.

**User Question:**
{user_input}

**DataFrame Name:** {df_name}

**Data Dictionary (Column Descriptions):**
{data_dict_text}

**Example Data (Top 2 Rows):**
{example_record}

**Instructions:**
1. Use Python code to answer the question.
2. Use pd.to_datetime() for dates if needed.
3. Do NOT use import statements.
4. Store the final answer in a variable named ANSWER.
5. Assume the DataFrame is already loaded as `{df_name}`.
"""

        try:
            # Get generated code
            response = model.generate_content(code_prompt)
            generated_code = response.text

            # Clean code
            clean_code = generated_code.strip()
            if clean_code.startswith("```"):
                clean_code = clean_code.strip("` \npython").strip("` \n")
            clean_code = "\n".join(
                line for line in clean_code.splitlines()
                if not line.strip().lower().startswith("import")
                and not line.strip().lower().startswith("from ")
            ).strip()

            # Show raw code
            with st.expander("📜 Show generated code"):
                st.code(clean_code, language="python")

            # Safe exec environment
            local_vars = {"df": df, "pd": pd, "datetime": datetime}
            exec(clean_code, {}, local_vars)
            ANSWER = local_vars.get("ANSWER", "No result returned.")

            # Step 2: Humanize the response
            explanation_prompt = f"""
You are a data assistant. Here's a user question and the raw Python result.
Generate a friendly explanation that clearly communicates the result in plain English.

**User Question:**  
{user_input}

**Raw Python Result:**  
{ANSWER}

**Friendly Answer:**  
"""
            human_response = model.generate_content(explanation_prompt)
            explanation = human_response.text.strip()

            # Show final answer
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

# --- Show Q&A History ---
if st.session_state.chat_history:
    st.markdown("## 🕓 Chat History")
    for entry in st.session_state.chat_history[::-1]:  # newest first
        st.markdown(f"**🧑‍💻 Question:** {entry['question']}")
        st.markdown(f"**🤖 Explanation:** {entry['explanation']}")
        with st.expander("🔍 Raw Result & Code"):
            st.write("**Raw Result:**")
            st.write(entry["raw_answer"])
            st.code(entry["code"], language="python")
