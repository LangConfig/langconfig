# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Quick test to understand the chunk structure from LangChain streaming"""

# Simulate the chunk structure we see in the logs
class AIMessageChunk:
    def __init__(self, content):
        self.content = content

# Test case 1: Empty content
chunk1 = AIMessageChunk(content=[])
print(f"Chunk 1 - Type: {type(chunk1)}, content type: {type(chunk1.content)}, value: {chunk1.content}")

# Test case 2: List with dict containing 'text' field (this is what we're seeing)
chunk2 = AIMessageChunk(content=[{'text': "I'll", 'type': 'text', 'index': 0}])
print(f"Chunk 2 - Type: {type(chunk2)}, content type: {type(chunk2.content)}, value: {chunk2.content}")

# Now test the extraction logic
def extract_token(chunk):
    token_text = None

    if chunk:
        # First check if chunk has a 'content' attribute
        if hasattr(chunk, 'content'):
            content = chunk.content
            # content might be a list of dicts like [{'text': 'hello', 'type': 'text'}]
            if isinstance(content, list) and len(content) > 0:
                # Extract text from list of content blocks
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and 'text' in item:
                        text_parts.append(item['text'])
                    elif isinstance(item, str):
                        text_parts.append(item)
                token_text = ''.join(text_parts) if text_parts else None
            elif isinstance(content, str):
                token_text = content
            else:
                token_text = str(content) if content else None

    return token_text

# Test the extraction
result1 = extract_token(chunk1)
print(f"\nExtracted from chunk1: type={type(result1)}, value={repr(result1)}")

result2 = extract_token(chunk2)
print(f"Extracted from chunk2: type={type(result2)}, value={repr(result2)}")

# Test concatenation
if result2:
    buffer = ""
    buffer += result2
    print(f"\nConcatenation test: '{buffer}' (type: {type(buffer)})")
