from .llm import complete

def extract(field_key, file_name, file_bytes, destination_country):
    prompt = f"""
    You are an expert Visa Document Analyst.
    Extract relevant information for the field '{field_key}' from the provided document for a visa application to {destination_country}.
    Provide accurate, clean, and concise extracted details.
    """
    
    # Pass file as a tuple of (filename, bytes) to llm.py
    files = [(file_name, file_bytes)] if file_bytes else None
    
    response_text = complete(prompt, files=files, max_tokens=1000)
    return response_text