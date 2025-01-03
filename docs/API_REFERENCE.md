### **API Documentation**

---

## **1. Upload Document**
**POST** `/upload-docs/`

- **Description**: Upload a `.doc` or `.docx` file.
- **Headers**:
  ```
  Content-Type: multipart/form-data
  ```
- **Request Body**:
  - **file** (`file`, required): The document file to upload (`.doc` or `.docx`).

- **Response Example (Success)**:
  **Status Code**: `200 OK`
  ```json
  {
    "message": "File uploaded successfully",
    "file_path": "./uploaded_files/document.docx"
  }
  ```

- **Response Example (Error - Invalid File Type)**:
  **Status Code**: `400 Bad Request`
  ```json
  {
    "error": "Only .doc or .docx files are allowed."
  }
  ```

---

## **2. List Uploaded Documents**
**GET** `/list-docs/`

- **Description**: Returns a list of uploaded `.doc` and `.docx` files.
  
- **Response Example (Success)**:
  **Status Code**: `200 OK`
  ```json
  {
    "files": ["file1.docx", "file2.doc"]
  }
  ```

---

## **3. Download Document**
**GET** `/download-docs/{file_name}`

- **Description**: Download a specific document file.
- **Path Parameter**:
  - **file_name** (`string`, required): The name of the file to download.
  
- **Response Example (Success)**:
  **Status Code**: `200 OK`  
  The file is returned for download.

- **Response Example (Error - File Not Found)**:
  **Status Code**: `404 Not Found`
  ```json
  {
    "error": "File not found"
  }
  ```