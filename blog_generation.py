import os
import re
from typing import Optional, Dict
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage

from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import MessageGraph
from langgraph.prebuilt import ToolNode
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langchain_groq import ChatGroq

# Load environment variables
load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
llm=ChatGroq(model="qwen-2.5-32b")


#api_key = os.getenv("OPENAI_API_KEY")
#llm = ChatOpenAI(model="gpt-4", openai_api_key=api_key, temperature=0.7)

os.environ["LANGSMITH_API_KEY"]=os.getenv("LANGCHAIN_API_KEY")

# Enable LangSmith tracing
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "Blog_Generator"

# Define state to track messages and feedback
class BlogState:
    def __init__(self, keyword: str):
        self.keyword = keyword
        self.blog_title: Optional[str] = None
        self.blog_content: Optional[str] = None
        self.feedback: Optional[str] = None  # ✅ Always initialized
        self.messages = []  # Used for tracking conversation flow

    def to_dict(self) -> Dict:
        """Convert state to dictionary for LangGraph."""
        return {
            "keyword": self.keyword,
            "blog_title": self.blog_title,
            "blog_content": self.blog_content,
            "feedback": self.feedback,  # ✅ Ensure feedback key exists
            "messages": self.messages
        }

# Function to generate blog title
def generate_title(state: Dict) -> Dict:
    prompt = f"Generate a catchy blog title for a blog on '{state['keyword']}'. The title should be engaging and under 60 characters."
    response = llm.invoke([HumanMessage(content=prompt)])
    
    state["blog_title"] = re.sub(r'[<>:"/\\|?*]', '', response.content.strip())  # ✅ Prevent invalid filename characters
    state["messages"].append(AIMessage(content=response.content))
    
    return state

# Function to generate blog content
def generate_content(state: Dict) -> Dict:
    prompt = f"Write a well-structured blog post based on the title: '{state['blog_title']}'. The blog should be **only 1-2 paragraphs long**, engaging, and informative. Do NOT repeat the title in the content."
    response = llm.invoke(state["messages"] + [HumanMessage(content=prompt)])
    
    state["blog_content"] = re.sub(r'</?[a-zA-Z]+>', '', response.content.strip())  # ✅ Clean unnecessary HTML tags
    state["messages"].append(AIMessage(content=response.content))
    
    return state

# Function to get user feedback
def human_feedback(state: Dict) -> Dict:
    print("\nGenerated Blog Title:\n" + state["blog_title"])
    print("\nGenerated Blog Content:\n" + state["blog_content"])

    while True:
        feedback = input("\nDoes the blog look good? (Yes/No): ").strip().lower()
        if feedback in ["yes", "no"]:
            state["feedback"] = feedback  # ✅ Store feedback
            return state
        print("Invalid input. Please enter only 'Yes' or 'No'.")

# Function to finalize and publish the blog
def finalize_blog(state: Dict) -> Dict:
    print("\nBlog has been published successfully!")
    return state  # ✅ Ensures proper exit

# Define workflow
workflow = StateGraph(dict)  # ✅ Fix: Use dictionary-based state
workflow.add_node("generate_title", generate_title)
workflow.add_node("generate_content", generate_content)
workflow.add_node("human_feedback", human_feedback)
workflow.add_node("finalize_blog", finalize_blog)
workflow.set_entry_point("generate_title")
workflow.add_edge("generate_title", "generate_content")
workflow.add_edge("generate_content", "human_feedback")

# ✅ FIX: Ensuring proper loop termination after blog finalization
workflow.add_conditional_edges(
    "human_feedback",
    lambda state: "generate_title" if state.get("feedback", "no") == "no" else "finalize_blog"
)
workflow.set_finish_point("finalize_blog")

# Run the workflow
def run_blog_generation():
    keyword = input("Enter the blog topic: ").strip()
    state = BlogState(keyword).to_dict()  # ✅ Convert instance to dictionary
    workflow_compiled = workflow.compile()

    for state in workflow_compiled.stream(state):
        if state.get("feedback", "no") == "yes":  # ✅ FIX: Avoid KeyError by using `.get()`
            print("\nWorkflow completed successfully.")
            break  # 🔥 Ensures proper exit after publishing

run_blog_generation()

