# PANDORA RAG HACKATHON 2026

> Source: `PANDORA RAG HACKATHON 2026 (1).pdf`
> Pandora Builderthon 2026 | RAG Knowledge Corpus — Pandora Knowledge Guardian Dataset

---

## Challenge Title

**Echoes of Pandora: An AI Knowledge Guardian for a Living Ecosystem**

## Theme

**Inspired by Avatar: The Way of Water**

## Challenge Duration

**5 Hours**

---

## Background

Pandora is a beautiful world where oceans, forests, wildlife, communities, and natural resources are deeply connected. However, information about environmental threats, marine species, community traditions, emergency procedures, research findings, and conservation activities is scattered across different reports, documents, field notes, and databases.

When an environmental incident occurs, such as water contamination, coral damage, illegal resource extraction, a wildlife emergency, or extreme weather, researchers and community leaders struggle to find accurate information quickly.

Traditional AI chatbots may provide incorrect or unsupported answers. Pandora therefore needs an intelligent system that can retrieve relevant information from trusted documents and generate reliable, context-aware responses.

---

## The Challenge

Your team must design and develop a **Retrieval-Augmented Generation application** called the **Pandora Knowledge Guardian**.

The system must help Pandora's environmental guardians, researchers, community leaders, and citizens access reliable information about the planet's ecosystem.

Users should be able to ask questions in natural language, and the system must retrieve relevant content from the provided knowledge base before generating its answer.

---

## Main Problem Statement

How can Retrieval-Augmented Generation be used to provide accurate, explainable, and context-aware solutions for environmental and community-related problems in Pandora?

Develop a working RAG application that allows users to upload or access Pandora-related documents and ask questions about environmental threats, marine ecosystems, conservation procedures, community knowledge, emergency responses, and sustainable resource management.

The generated answers must be based on the retrieved documents rather than unsupported assumptions.

---

## Example Scenario

A section of Pandora's ocean has suddenly changed colour, and several aquatic creatures have begun leaving the area.

A guardian may ask:

> "What could be causing the change in water colour, which species may be affected, and what immediate actions should our response team take?"

The system should:

1. Search the available environmental reports and field documents.
2. Retrieve the most relevant information.
3. Generate a clear recommended response.
4. Show the sources used to create the answer.
5. Clearly state when sufficient information is unavailable.

---

## Minimum Functional Requirements

### 1. Knowledge-Base Management

The application must allow users to upload or use documents such as:

- Environmental reports
- Marine-life records
- Emergency-response guidelines
- Community knowledge documents
- Conservation policies
- Research notes
- Water-quality reports

The system should support at least one common document format, such as PDF, TXT, CSV, or DOCX.

### 2. Document Processing

The application must:

- Extract text from the documents.
- Divide the content into meaningful chunks.
- Generate vector embeddings.
- Store the embeddings in a vector database or vector index.

### 3. Semantic Retrieval

When a user submits a question, the application must retrieve the most relevant document chunks using semantic search.

### 4. AI-Generated Responses

The system must generate an answer using:

- The user's question
- The retrieved context
- A suitable large language model

The answer should not rely only on the language model's general knowledge.

### 5. Source References

Every generated answer must display its supporting source information, such as:

- Document name
- Section or page number
- Retrieved text excerpt
- Relevance score, where applicable

### 6. Uncertainty Handling

When the knowledge base does not contain enough information, the system should clearly respond with a message such as:

> "The available Pandora knowledge base does not contain sufficient evidence to answer this question."

The system should not invent unsupported information.

### 7. User Interface

Create a simple and usable interface containing:

- A document-upload area
- A question-input area
- A generated-answer section
- A retrieved-sources section
- A clear or reset option

The interface should follow a visual theme inspired by Pandora's oceans, bioluminescent environment, nature, and interconnected ecosystem.

---

## Required Use Cases

The completed application should demonstrate **at least three** of the following use cases:

### Environmental Incident Investigation
Identify possible causes, affected areas, risks, and recommended actions for an environmental incident.

### Marine-Life Protection
Retrieve information about aquatic species, habitats, threats, and protection procedures.

### Emergency Response
Provide context-based instructions for floods, storms, water contamination, forest damage, or wildlife emergencies.

### Community Knowledge Assistant
Answer questions using the cultural practices, traditional ecological knowledge, and conservation principles of Pandora's communities.

### Sustainable Resource Management
Provide recommendations for using water, energy, forests, and marine resources responsibly.

### Research Assistant
Summarize reports, compare documents, identify patterns, and extract important findings from Pandora's research documents.

---

## Technical Expectations

Teams may use any suitable technologies.

Possible technologies include:

- Python, JavaScript, TypeScript, Java, or Ballerina
- LangChain, LlamaIndex, Haystack, or a custom RAG pipeline
- OpenAI, Gemini, Claude, Llama, Mistral, or another suitable language model
- Qdrant, ChromaDB, Pinecone, FAISS, Weaviate, or another vector database
- Next.js, React, Streamlit, Gradio, or another frontend framework

The judges will evaluate the completed solution rather than the specific technology stack.

---

## Optional Advanced Features

Teams may gain additional marks by implementing one or more of the following:

- Hybrid search using semantic and keyword retrieval
- Metadata-based filtering
- Query rewriting
- Reranking retrieved results
- Conversation memory
- Multiple-document comparison
- Role-based answers for researchers, guardians, and citizens
- Voice-based questions
- Multilingual support
- Image or map-based retrieval
- Emergency-priority classification
- Answer-confidence scoring
- Knowledge-graph integration
- Agentic RAG workflow

---

## Expected Final Submission

Each team must submit:

1. A working RAG application.
2. A GitHub repository containing the source code.
3. A README file containing setup and usage instructions.
4. A short architecture diagram.
5. A demonstration using at least three questions.
6. Evidence of the retrieved sources used for each answer.
7. A three-to-five-minute final presentation.

---

## Suggested Demonstration Questions

Teams may use these questions or create their own:

1. What are the possible causes of unusual changes in Pandora's ocean water?
2. Which marine species are most vulnerable to water contamination?
3. What immediate actions should guardians take after detecting coral damage?
4. Compare the recommended responses for water contamination and an underwater volcanic event.
5. What traditional community practices can support marine conservation?
6. Summarize the major environmental threats mentioned across the uploaded reports.
7. Which areas should receive emergency attention first, based on the available evidence?

---

## Evaluation Criteria

### RAG Architecture and Retrieval Quality — 25 Marks
- Effective document processing
- Appropriate chunking strategy
- Relevant document retrieval
- Suitable vector-storage implementation

### Accuracy and Grounded Responses — 20 Marks
- Answers are based on retrieved information
- Hallucinations are minimized
- Insufficient evidence is handled correctly

### Real-World Problem Solving — 20 Marks
- The solution addresses a meaningful Pandora-related problem
- Recommendations are practical and clearly explained
- The application demonstrates environmental or community value

### User Interface and Experience — 15 Marks
- Clear and usable interface
- Well-organized answers and sources
- Visual connection to the Pandora theme

### Innovation — 10 Marks
- Creative use of RAG
- Advanced retrieval, reasoning, or interaction features
- Unique problem-solving approach

### Presentation and Documentation — 10 Marks
- Clear final demonstration
- Understandable architecture
- Well-organized code and documentation

**Total: 100 Marks**

---

## Rules and Constraints

- The solution must be developed within five hours.
- The core application must use Retrieval-Augmented Generation.
- A normal chatbot without document retrieval will not qualify as a complete solution.
- Teams may use open-source frameworks, APIs, and pretrained models.
- Teams must disclose any prebuilt components used.
- The final demonstration must show both the generated answer and its supporting sources.
- The solution should not produce fabricated information when relevant evidence is unavailable.

---

## Final Mission

Build an intelligent knowledge system that protects the balance between Pandora's people, oceans, wildlife, and natural resources by transforming scattered information into reliable and actionable knowledge.

**The strongest solution will not simply generate answers—it will retrieve evidence, explain its reasoning, acknowledge uncertainty, and help Pandora make better decisions.**

This challenge is technically achievable within five hours while still allowing strong teams to demonstrate advanced features and innovation.
