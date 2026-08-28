from unstructured.partition.pdf import partition_pdf

filepath= r'/MCP_RAG_BOT/ProvisionalDegree.pdf'

def create_chunks_from_pdf(file_path):

    elements = partition_pdf(
        filename=file_path,
        strategy="fast",
        infer_table_structure=True,
    )
    # → elements is a flat list of Table and CompositeElement objects
    #   passed to table_text_segregation() and get_images() in ingest_pdfs()
    return elements

elements = create_chunks_from_pdf(filepath)

for el in elements:
    print(el.text)