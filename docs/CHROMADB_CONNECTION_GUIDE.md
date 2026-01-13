# ChromaDB Connection Guide

## 🔌 Methods to Connect to ChromaDB

ChromaDB supports **3 main modes**:

### 1. **Persistent Client** (Currently Used) ✅
Saves data to disk, persists after restart

```python
import chromadb

# Connect to local ChromaDB
client = chromadb.PersistentClient(path="./chroma_db")

# Get collection
collection = client.get_collection("cv_embeddings")

# View data
print(f"Total embeddings: {collection.count()}")
```

---

### 2. **HTTP Client** (Client-Server mode)
Connect to remote ChromaDB server (for production/team collaboration)

```python
import chromadb

# Connect to ChromaDB server
client = chromadb.HttpClient(host="localhost", port=8001)

# Get collection
collection = client.get_collection("cv_embeddings")
```

**Start ChromaDB server:**
```bash
# Install ChromaDB with server
uv pip install 'chromadb[server]'

# Run server (use different port from FastAPI - 8000)
uv run chroma run --path ./chroma_db --port 8001
```

**⚠️ Note:** ChromaDB server only exposes REST API, NO web UI. To view data, use Python scripts or CLI tools.

---

### 3. **In-Memory Client** (Testing only)
Data only in RAM, lost on restart

```python
import chromadb

# In-memory client (no persistence)
client = chromadb.Client()

# Get/create collection
collection = client.get_or_create_collection("test")
```

---

## 🔍 Methods to View Data in ChromaDB

### Method 1: Python Script
```python
import chromadb
from pathlib import Path

# Connect
client = chromadb.PersistentClient(path="./chroma_db")

# List all collections
print("Collections:", client.list_collections())

# Get collection
cv_collection = client.get_collection("cv_embeddings")
jd_collection = client.get_collection("jd_embeddings")

# View stats
print(f"CV embeddings: {cv_collection.count()}")
print(f"JD embeddings: {jd_collection.count()}")

# Get all data
all_cvs = cv_collection.get(include=["metadatas", "documents"])
print(f"First CV: {all_cvs['metadatas'][0]}")
```

---

### Method 2: CLI Tool (Custom)

Use the pre-built `tools/chroma_inspector.py`:

```bash
# View all collections
uv run python tools/chroma_inspector.py --list

# View CV embeddings
uv run python tools/chroma_inspector.py --collection cv_embeddings

# View statistics
uv run python tools/chroma_inspector.py --stats

# Export to JSON
uv run python tools/chroma_inspector.py --export data.json --collection cv_embeddings
```

---

### Method 3: Third-party Web UI (Optional)

**⚠️ ChromaDB server does NOT have built-in web UI**

If you want a web interface, use third-party tools:

```bash
# Option 1: chroma-ui (Third-party)
git clone https://github.com/thakkaryash94/chroma-ui.git
cd chroma-ui
npm install
npm run dev

# Configure to connect to ChromaDB server
```

**Note:** Not recommended for local development, CLI tools are sufficient.

---

### Method 4: Jupyter Notebook
```python
import chromadb
imp

### Method 4: CLI Script (Create custom tool)

I will create a `chroma_inspector.py` file for you to use:

```bash
# View all collections
python chroma_inspector.py --list

# View CV embeddings
python chroma_inspector.py --collection cv_embeddings

# Search similar CVs
python chroma_inspector.py --search "Python developer"

# Clear cache
python chroma_inspector.py --clear cv_embeddings
```

---

## 🛠️ Tools & Libraries

### 1. **ChromaDB Python Client** (Official)
```python
import chromadb

client = chromadb.PersistentClient(path="./chroma_db")
```

### 3. **SQLite Browser** (View metadata only)
- ChromaDB uses SQLite to store metadata
- Can view metadata (cannot view embeddings) using SQLite browser

```bash
# macOS
brew install --cask db-browser-for-sqlite

# Open ChromaDB metadata
open chroma_db/chroma.sqlite3
```
- ChromaDB is not an SQL database → DBeaver does not support directly
- But can use SQLite to view metadata (if ChromaDB uses SQLite backend)

---

## 📊 Inspect ChromaDB Structure

### File structure:
```
chroma_db/
├── chroma.sqlite3           # Metadata database
├── cv_embeddings/           # Collection data
│   ├── data_level0.bin      # Vector data
│   └── header.bin           # Header info
└── jd_embeddings/
    ├── data_level0.bin
    └── header.bin
```

### View metadata (SQLite):
```bash
# ChromaDB uses SQLite to store metadata
sqlite3 chroma_db/chroma.sqlite3

# SQL queries
sqlite> .tables
sqlite> SELECT * FROM collections;
sqlite> SELECT * FROM embeddings LIMIT 10;
```

---

## 🔐 Connection Security

### Local development (current):
```python
# No authentication needed
client = chromadb.PersistentClient(path="./chroma_db")
```

### Production (with server):
```python
# With authentication
import chromadb
from chromadb.config import Settings

client = chromadb.HttpClient(
    host="production.server.com",
    port=8000,
    settings=Settings(
        chroma_client_auth_provider="token",
        chroma_client_auth_credentials="your-secret-token"
    )
)
```

---

## 🚀 Quick Start Examples

### Example 1: Check if cache exists
```python
import chromadb

client = chromadb.PersistentClient(path="./chroma_db")

try:
    cv_collection = client.get_collection("cv_embeddings")
    print(f"✅ Cache exists: {cv_collection.count()} embeddings")
except:
    print("❌ No cache found")
```

### Example 2: View top 5 cached CVs
```python
import chromadb

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_collection("cv_embeddings")

data = collection.get(limit=5, include=["metadatas"])
for i, metadata in enumerate(data['metadatas'], 1):
    print(f"{i}. {metadata['filename']} (ID: {metadata['file_id']})")
```

### Example 3: Search similar embeddings
```python
import chromadb

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_collection("cv_embeddings")

# Assuming you have a query embedding
query_embedding = [0.1, 0.2, ...]  # 1536-dim vector

results = collection.query(
    query_embeddings=[query_embedding],
    n_results=5,
    include=["metadatas", "distances"]
)

print("Top 5 similar CVs:")
for i, (metadata, distance) in enumerate(zip(results['metadatas'][0], results['distances'][0]), 1):
    similarity = 1 - distance
    print(f"{i}. {metadata['filename']}: {similarity:.2%}")
```

---

## 🎯 Best Practices

1. **Always use PersistentClient** for production
   ```python
   client = chromadb.PersistentClient(path="./chroma_db")
   ```

2. **Backup ChromaDB directory** regularly
   ```bash
   tar -czf chroma_backup_$(date +%Y%m%d).tar.gz chroma_db/
   ```

3. **Monitor collection size**
   ```python
   collection = client.get_collection("cv_embeddings")
   print(f"Embeddings: {collection.count()}")
   ```

4. **Clear old cache** when needed
   ```python
   client.delete_collection("cv_embeddings")
   ```

---

## 🔧 Troubleshooting

### Problem: "Collection not found"
```python
# Solution: Create collection if not exists
collection = client.get_or_create_collection("cv_embeddings")
```

### Problem: "Permission denied"
```bash
# Solution: Fix permissions
chmod -R 755 chroma_db/
```

### Problem: "Database locked"
```python
# Solution: Close all connections first
client = None  # Release connection
import time
time.sleep(1)
client = chromadb.PersistentClient(path="./chroma_db")
```

---

## 📚 Resources

- **Official Docs**: https://docs.trychroma.com/
- **GitHub**: https://github.com/chroma-core/chroma
- **Discord**: https://discord.gg/MMeYNTmh3x
- **API Reference**: https://docs.trychroma.com/reference/Client

### 2. **LangChain Integration**
```python
from langchain.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings

vectorstore = Chroma(
    persist_directory="./chroma_db",
    embedding_function=OpenAIEmbeddings(),
    collection_name="cv_embeddings"
)

# Query
results = vectorstore.similarity_search("Python developer", k=5)
```SQLite Browser** (View metadata only)
- ChromaDB dùng SQLite để lưu metadata
- Có thể xem metadata (không xem được embeddings) bằng SQLite browser

```bash
# macOS
brew install --cask db-browser-for-sqlite

# Open ChromaDB metadata
open chroma_db/chroma.sqlite3
```
- ChromaDB không phải SQL database → DBeaver không support trực tiếp
- Nhưng có thể dùng SQLite để xem metadata (nếu ChromaDB dùng SQLite backend)

---

## 📊 Inspect ChromaDB Structure

### File structure:
```
chroma_db/
├── chroma.sqlite3           # Metadata database
├── cv_embeddings/           # Collection data
│   ├── data_level0.bin      # Vector data
│   └── header.bin           # Header info
└── jd_embeddings/
    ├── data_level0.bin
    └── header.bin
```

### View metadata (SQLite):
```bash
# ChromaDB dùng SQLite để lưu metadata
sqlite3 chroma_db/chroma.sqlite3

# SQL queries
sqlite> .tables
sqlite> SELECT * FROM collections;
sqlite> SELECT * FROM embeddings LIMIT 10;
```

---

## 🔐 Connection Security

### Local development (hiện tại):
```python
# No authentication needed
client = chromadb.PersistentClient(path="./chroma_db")
```

### Production (with server):
```python
# With authentication
import chromadb
from chromadb.config import Settings

client = chromadb.HttpClient(
    host="production.server.com",
    port=8000,
    settings=Settings(
        chroma_client_auth_provider="token",
        chroma_client_auth_credentials="your-secret-token"
    )
)
```

---

## 🚀 Quick Start Examples

### Example 1: Check if cache exists
```python
import chromadb

client = chromadb.PersistentClient(path="./chroma_db")

try:
    cv_collection = client.get_collection("cv_embeddings")
    print(f"✅ Cache exists: {cv_collection.count()} embeddings")
except:
    print("❌ No cache found")
```

### Example 2: View top 5 cached CVs
```python
import chromadb

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_collection("cv_embeddings")

data = collection.get(limit=5, include=["metadatas"])
for i, metadata in enumerate(data['metadatas'], 1):
    print(f"{i}. {metadata['filename']} (ID: {metadata['file_id']})")
```

### Example 3: Search similar embeddings
```python
import chromadb

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_collection("cv_embeddings")

# Assuming you have a query embedding
query_embedding = [0.1, 0.2, ...]  # 1536-dim vector

results = collection.query(
    query_embeddings=[query_embedding],
    n_results=5,
    include=["metadatas", "distances"]
)

print("Top 5 similar CVs:")
for i, (metadata, distance) in enumerate(zip(results['metadatas'][0], results['distances'][0]), 1):
    similarity = 1 - distance
    print(f"{i}. {metadata['filename']}: {similarity:.2%}")
```

---

## 🎯 Best Practices

1. **Always use PersistentClient** cho production
   ```python
   client = chromadb.PersistentClient(path="./chroma_db")
   ```

2. **Backup ChromaDB directory** định kỳ
   ```bash
   tar -czf chroma_backup_$(date +%Y%m%d).tar.gz chroma_db/
   ```

3. **Monitor collection size**
   ```python
   collection = client.get_collection("cv_embeddings")
   print(f"Embeddings: {collection.count()}")
   ```

4. **Clear old cache** khi cần
   ```python
   client.delete_collection("cv_embeddings")
   ```

---

## 🔧 Troubleshooting

### Problem: "Collection not found"
```python
# Solution: Create collection if not exists
collection = client.get_or_create_collection("cv_embeddings")
```

### Problem: "Permission denied"
```bash
# Solution: Fix permissions
chmod -R 755 chroma_db/
```

### Problem: "Database locked"
```python
# Solution: Close all connections first
client = None  # Release connection
import time
time.sleep(1)
client = chromadb.PersistentClient(path="./chroma_db")
```

---

## 📚 Resources

- **Official Docs**: https://docs.trychroma.com/
- **GitHub**: https://github.com/chroma-core/chroma
- **Discord**: https://discord.gg/MMeYNTmh3x
- **API Reference**: https://docs.trychroma.com/reference/Client
