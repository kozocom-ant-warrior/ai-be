#!/usr/bin/env python3
"""
ChromaDB Inspector Tool

Công cụ CLI để inspect và quản lý ChromaDB cache

Usage:
    python chroma_inspector.py --list                           # List all collections
    python chroma_inspector.py --stats                          # Show statistics
    python chroma_inspector.py --collection cv_embeddings       # View collection details
    python chroma_inspector.py --search "Python developer"      # Search similar CVs
    python chroma_inspector.py --clear cv_embeddings            # Clear collection
    python chroma_inspector.py --export cv_embeddings.json      # Export to JSON
"""

import argparse
import json
import chromadb
from pathlib import Path
from typing import Optional
import sys

# ChromaDB path (relative to project root, same as in vector_db.py)
CHROMA_DB_PATH = Path(__file__).parent.parent.parent / "db" / "chroma_db"


def get_client():
    """Get ChromaDB client"""
    if not CHROMA_DB_PATH.exists():
        print(f"❌ ChromaDB not found at: {CHROMA_DB_PATH}")
        print(f"   Run the application first to create the database.")
        sys.exit(1)
    
    return chromadb.PersistentClient(path=str(CHROMA_DB_PATH))


def list_collections():
    """List all collections"""
    client = get_client()
    collections = client.list_collections()
    
    if not collections:
        print("📂 No collections found")
        return
    
    print(f"📂 Collections ({len(collections)}):")
    print("-" * 80)
    for coll in collections:
        count = coll.count()
        print(f"  • {coll.name}: {count:,} embeddings")
    print("-" * 80)


def show_stats():
    """Show detailed statistics"""
    client = get_client()
    collections = client.list_collections()
    
    print("=" * 80)
    print("📊 ChromaDB Statistics")
    print("=" * 80)
    print(f"Database path: {CHROMA_DB_PATH}")
    print(f"Total collections: {len(collections)}")
    print()
    
    total_embeddings = 0
    for coll in collections:
        count = coll.count()
        total_embeddings += count
        
        print(f"Collection: {coll.name}")
        print(f"  - Embeddings: {count:,}")
        
        # Get sample data
        if count > 0:
            sample = coll.get(limit=1, include=["metadatas"])
            if sample['metadatas']:
                print(f"  - Sample metadata: {sample['metadatas'][0]}")
        print()
    
    print(f"Total embeddings: {total_embeddings:,}")
    print("=" * 80)


def view_collection(collection_name: str, limit: int = 10):
    """View collection details"""
    client = get_client()
    
    try:
        collection = client.get_collection(collection_name)
    except Exception as e:
        print(f"❌ Collection '{collection_name}' not found")
        print(f"   Available collections: {[c.name for c in client.list_collections()]}")
        return
    
    count = collection.count()
    print(f"📄 Collection: {collection_name}")
    print(f"   Total embeddings: {count:,}")
    print()
    
    if count == 0:
        print("   (Empty collection)")
        return
    
    # Get all data
    data = collection.get(
        limit=min(limit, count),
        include=["metadatas", "documents"]
    )
    
    print(f"Showing first {len(data['ids'])} items:")
    print("-" * 80)
    
    for i, (doc_id, metadata, document) in enumerate(zip(
        data['ids'], 
        data['metadatas'], 
        data['documents']
    ), 1):
        print(f"{i}. ID: {doc_id}")
        print(f"   Metadata: {metadata}")
        print(f"   Document preview: {document[:100]}...")
        print()
    
    print("-" * 80)


def search_similar(query_text: str, collection_name: str = "cv_embeddings", top_k: int = 5):
    """Search similar embeddings"""
    client = get_client()
    
    try:
        collection = client.get_collection(collection_name)
    except Exception as e:
        print(f"❌ Collection '{collection_name}' not found")
        return
    
    # For search, we need an embedding
    # This is simplified - in reality you'd need to generate embedding from query_text
    print(f"⚠️  Search requires embedding generation")
    print(f"   Query: '{query_text}'")
    print(f"   To implement: Generate embedding from query, then use collection.query()")
    print()
    print("Example code:")
    print(f"""
    from openai import OpenAI
    client_openai = OpenAI(api_key="your-key")
    
    # Generate embedding for query
    response = client_openai.embeddings.create(
        model="text-embedding-3-small",
        input="{query_text}"
    )
    query_embedding = response.data[0].embedding
    
    # Search
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results={top_k},
        include=["metadatas", "distances"]
    )
    
    for metadata, distance in zip(results['metadatas'][0], results['distances'][0]):
        similarity = 1 - distance
        print(f"{{metadata['filename']}}: {{similarity:.2%}}")
    """)


def clear_collection(collection_name: str, confirm: bool = False):
    """Clear collection"""
    client = get_client()
    
    try:
        collection = client.get_collection(collection_name)
        count = collection.count()
    except Exception as e:
        print(f"❌ Collection '{collection_name}' not found")
        return
    
    if not confirm:
        response = input(f"⚠️  Delete {count:,} embeddings from '{collection_name}'? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled")
            return
    
    client.delete_collection(collection_name)
    print(f"✅ Deleted collection '{collection_name}' ({count:,} embeddings)")


def export_collection(collection_name: str, output_file: str):
    """Export collection to JSON"""
    client = get_client()
    
    try:
        collection = client.get_collection(collection_name)
    except Exception as e:
        print(f"❌ Collection '{collection_name}' not found")
        return
    
    print(f"📤 Exporting collection '{collection_name}'...")
    
    # Get all data (without embeddings to save space)
    data = collection.get(include=["metadatas", "documents"])
    
    export_data = {
        "collection_name": collection_name,
        "total_count": len(data['ids']),
        "items": []
    }
    
    for doc_id, metadata, document in zip(data['ids'], data['metadatas'], data['documents']):
        export_data["items"].append({
            "id": doc_id,
            "metadata": metadata,
            "document_preview": document[:500]  # Only first 500 chars
        })
    
    # Get absolute path for output file
    import os
    output_path = os.path.abspath(output_file)
    
    # Save to file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Exported {len(data['ids']):,} items to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="ChromaDB Inspector Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python chroma_inspector.py --list
  python chroma_inspector.py --stats
  python chroma_inspector.py --collection cv_embeddings
  python chroma_inspector.py --collection cv_embeddings --limit 20
  python chroma_inspector.py --search "Python developer"
  python chroma_inspector.py --clear cv_embeddings
  python chroma_inspector.py --export cv_embeddings.json --collection cv_embeddings
        """
    )
    
    parser.add_argument('--list', action='store_true', help='List all collections')
    parser.add_argument('--stats', action='store_true', help='Show statistics')
    parser.add_argument('--collection', type=str, help='View collection details')
    parser.add_argument('--limit', type=int, default=10, help='Limit results (default: 10)')
    parser.add_argument('--search', type=str, help='Search similar items (query text)')
    parser.add_argument('--clear', type=str, help='Clear collection (name)')
    parser.add_argument('--export', type=str, help='Export to JSON file')
    parser.add_argument('--yes', action='store_true', help='Skip confirmation prompts')
    
    args = parser.parse_args()
    
    # If no arguments, show help
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)
    
    try:
        if args.list:
            list_collections()
        
        elif args.stats:
            show_stats()
        
        elif args.export:
            if not args.collection:
                print("❌ --export requires --collection")
                sys.exit(1)
            # Export only - don't show collection view
            export_collection(args.collection, args.export)
        
        elif args.collection:
            view_collection(args.collection, args.limit)
        
        elif args.search:
            search_similar(args.search)
        
        elif args.clear:
            clear_collection(args.clear, args.yes)
        
        else:
            parser.print_help()
    
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
