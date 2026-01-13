"""Interactive cache management tool - Clear all or specific collections"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db import vector_db

def print_menu():
    """Display cache clearing menu"""
    print("\n" + "=" * 80)
    print("🗑️  CACHE MANAGEMENT TOOL")
    print("=" * 80)
    print("\nAvailable options:")
    print("  1. Clear ALL caches (5 collections)")
    print("  2. Clear Stage 0 only (CV + JD embeddings)")
    print("  3. Clear Stage 1A only (JD requirements)")
    print("  4. Clear Stage 1B only (CV extraction)")
    print("  5. Clear Stage 3 only (Advanced features)")
    print("  6. Exit")
    print("=" * 80)

def show_collections():
    """Show all collection names"""
    print("\n📦 Collection mapping:")
    print(f"  - cv_embeddings          → Stage 0: CV embeddings")
    print(f"  - jd_embeddings          → Stage 0: JD embeddings")
    print(f"  - jd_requirements_data   → Stage 1A: JD requirements extraction")
    print(f"  - cv_extracted_data      → Stage 1B: CV extraction")
    print(f"  - advanced_features      → Stage 3: Advanced features")

def clear_all():
    """Clear all caches"""
    print("\n⚠️  WARNING: This will clear ALL 5 collections!")
    show_collections()
    confirm = input("\n⚠️  Continue? (y/N): ")
    
    if confirm.lower() != 'y':
        print("❌ Cancelled")
        return
    
    success_count, failed = vector_db.clear_cache()
    show_results(success_count, failed, 5)

def clear_stage_0():
    """Clear Stage 0: Embeddings (CV + JD)"""
    print("\n📊 Clearing Stage 0: CV + JD Embeddings")
    print("  - cv_embeddings")
    print("  - jd_embeddings")
    
    confirm = input("\n⚠️  Continue? (y/N): ")
    if confirm.lower() != 'y':
        print("❌ Cancelled")
        return
    
    success = 0
    failed = []
    
    s, f = vector_db.clear_cache("cv_embeddings")
    success += s
    failed.extend(f)
    
    s, f = vector_db.clear_cache("jd_embeddings")
    success += s
    failed.extend(f)
    
    show_results(success, failed, 2)

def clear_stage_1a():
    """Clear Stage 1A: JD requirements"""
    print("\n📊 Clearing Stage 1A: JD Requirements Extraction")
    print("  - jd_requirements_data")
    
    confirm = input("\n⚠️  Continue? (y/N): ")
    if confirm.lower() != 'y':
        print("❌ Cancelled")
        return
    
    success, failed = vector_db.clear_cache("jd_requirements_data")
    show_results(success, failed, 1)

def clear_stage_1b():
    """Clear Stage 1B: CV extraction"""
    print("\n📊 Clearing Stage 1B: CV Extraction")
    print("  - cv_extracted_data")
    
    confirm = input("\n⚠️  Continue? (y/N): ")
    if confirm.lower() != 'y':
        print("❌ Cancelled")
        return
    
    success, failed = vector_db.clear_cache("cv_extracted_data")
    show_results(success, failed, 1)

def clear_stage_3():
    """Clear Stage 3: Advanced features"""
    print("\n📊 Clearing Stage 3: Advanced Features")
    print("  - advanced_features")
    
    confirm = input("\n⚠️  Continue? (y/N): ")
    if confirm.lower() != 'y':
        print("❌ Cancelled")
        return
    
    success, failed = vector_db.clear_cache("advanced_features")
    show_results(success, failed, 1)

def show_results(success_count, failed, total):
    """Show clearing results"""
    print("\n" + "=" * 80)
    print("📊 CACHE CLEARING RESULTS")
    print("=" * 80)
    print(f"✅ Successfully cleared: {success_count}/{total} collection(s)")
    
    if failed:
        print(f"⚠️  Failed to clear: {len(failed)} collection(s)")
        for coll in failed:
            print(f"   - {coll} (may not exist)")
    else:
        print("✅ All requested collections cleared successfully!")
    print("=" * 80)

def main():
    """Main interactive loop"""
    # Check for command-line arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        
        if arg in ['--all', '-a']:
            clear_all()
        elif arg in ['--stage0', '-s0']:
            clear_stage_0()
        elif arg in ['--stage1a', '-s1a']:
            clear_stage_1a()
        elif arg in ['--stage1b', '-s1b']:
            clear_stage_1b()
        elif arg in ['--stage3', '-s3']:
            clear_stage_3()
        elif arg in ['--help', '-h']:
            print("Usage: python clear_cache.py [option]")
            print("\nOptions:")
            print("  --all, -a       Clear all caches")
            print("  --stage0, -s0   Clear Stage 0 (embeddings)")
            print("  --stage1a, -s1a Clear Stage 1A (JD requirements)")
            print("  --stage1b, -s1b Clear Stage 1B (CV extraction)")
            print("  --stage3, -s3   Clear Stage 3 (advanced features)")
            print("  --help, -h      Show this help")
            print("\nRun without arguments for interactive menu.")
        else:
            print(f"❌ Unknown option: {arg}")
            print("Run with --help for usage information.")
        return
    
    # Interactive menu
    while True:
        print_menu()
        choice = input("\nSelect option (1-6): ").strip()
        
        if choice == '1':
            clear_all()
        elif choice == '2':
            clear_stage_0()
        elif choice == '3':
            clear_stage_1a()
        elif choice == '4':
            clear_stage_1b()
        elif choice == '5':
            clear_stage_3()
        elif choice == '6':
            print("\n👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please select 1-6.")
        
        # Ask if continue
        continue_choice = input("\n🔄 Clear more caches? (y/N): ")
        if continue_choice.lower() != 'y':
            print("\n👋 Goodbye!")
            break

if __name__ == "__main__":
    main()
