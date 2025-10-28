"""
Interactive batch processor - Process one file at a time with user confirmation.
"""

import os
import sys
from pathlib import Path
import logging
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import process_document


def setup_logging(log_dir: Path) -> logging.Logger:
    """Setup logging."""
    log_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"interactive_{timestamp}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)


def main():
    """Interactive batch processing - one file at a time."""
    
    # Paths
    input_dir = Path("data/raw_pdfs/THONGBAO")
    json_dir = Path("data/processed/json")
    csv_dir = Path("data/processed/csv")
    log_dir = Path("data/logs")
    
    # Create directories
    json_dir.mkdir(parents=True, exist_ok=True)
    csv_dir.mkdir(parents=True, exist_ok=True)
    
    # Setup logging
    logger = setup_logging(log_dir)
    
    # Find PDFs
    pdf_files = sorted(input_dir.glob("*.pdf"))
    
    print("="*80)
    print(f"🎯 INTERACTIVE BATCH PROCESSING - {len(pdf_files)} files")
    print("="*80)
    print(f"Input:  {input_dir}")
    print(f"Output: json={json_dir}, csv={csv_dir}")
    print("="*80)
    print()
    
    # Stats
    success = 0
    failed = 0
    skipped = 0
    stopped = 0
    
    # Process each file
    for idx, pdf_path in enumerate(pdf_files, 1):
        file_name = pdf_path.stem
        json_output = json_dir / f"{file_name}_output.json"
        
        # Skip if exists
        if json_output.exists():
            print(f"[{idx}/{len(pdf_files)}] ⏭️  SKIP: {pdf_path.name} (already processed)")
            skipped += 1
            
            # Ask if continue
            choice = input("\nContinue to next file? (y/n/q to quit): ").strip().lower()
            if choice == 'q':
                stopped = idx - success - failed - skipped
                print("\n⚠️  Stopped by user")
                break
            elif choice == 'n':
                continue
            else:
                continue
        
        print(f"\n{'='*80}")
        print(f"[{idx}/{len(pdf_files)}] 🔄 Processing: {pdf_path.name}")
        print(f"{'='*80}")
        
        try:
            # Process with main.py logic
            result = process_document(str(pdf_path))
            
            if result:
                # Files are already saved by process_document()
                # Just move them to correct location
                import shutil
                
                # Move JSON
                src_json = Path(f"{file_name}_output.json")
                if src_json.exists():
                    shutil.move(str(src_json), str(json_output))
                    print(f"✅ Saved: {json_output}")
                
                # Move CSVs
                src_doc_csv = Path(f"{file_name}_document.csv")
                src_chunks_csv = Path(f"{file_name}_chunks.csv")
                
                if src_doc_csv.exists():
                    dest = csv_dir / src_doc_csv.name
                    shutil.move(str(src_doc_csv), str(dest))
                    print(f"✅ Saved: {dest}")
                
                if src_chunks_csv.exists():
                    dest = csv_dir / src_chunks_csv.name
                    shutil.move(str(src_chunks_csv), str(dest))
                    print(f"✅ Saved: {dest}")
                    
                    # Count chunks
                    import csv
                    with open(dest, 'r', encoding='utf-8-sig') as f:
                        reader = csv.DictReader(f)
                        chunks = list(reader)
                        print(f"📊 Chunks extracted: {len(chunks)}")
                
                success += 1
                logger.info(f"✅ SUCCESS: {pdf_path.name}")
                
                print(f"\n{'─'*80}")
                print(f"✅ SUCCESS - File {idx}/{len(pdf_files)} completed!")
                print(f"   Progress: ✅ {success} | ⏭️  {skipped} | ❌ {failed} | ⏸️  {len(pdf_files) - idx} remaining")
                print(f"{'─'*80}")
            else:
                failed += 1
                logger.error(f"❌ FAILED: {pdf_path.name} - No result")
                print(f"❌ FAILED: No result returned")
        
        except Exception as e:
            failed += 1
            logger.error(f"❌ ERROR: {pdf_path.name} - {e}")
            print(f"❌ ERROR: {e}")
        
        # Ask user what to do next
        print()
        print("Options:")
        print("  [Enter] - Continue to next file")
        print("  v - View JSON output")
        print("  c - View CSV chunks")
        print("  q - Quit")
        
        choice = input("Your choice: ").strip().lower()
        
        if choice == 'q':
            stopped = len(pdf_files) - idx
            print("\n⚠️  Stopped by user")
            break
        elif choice == 'v' and json_output.exists():
            import json
            with open(json_output, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"\n📄 Document: {data['document_metadata'].get('DOC_TITLE', 'N/A')}")
                print(f"📊 Chunks: {len(data.get('chunk_metadata', []))}")
            input("\nPress Enter to continue...")
        elif choice == 'c':
            csv_path = csv_dir / f"{file_name}_chunks.csv"
            if csv_path.exists():
                import csv
                with open(csv_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    for i, row in enumerate(reader, 1):
                        if i <= 3:  # Show first 3 chunks
                            print(f"\nChunk {i}:")
                            print(f"  Topic: {row.get('CHUNK_TOPIC', 'N/A')}")
                            print(f"  Text: {row.get('chunk_text', 'N/A')[:100]}...")
                input("\nPress Enter to continue...")
    
    # Summary
    print("\n" + "="*80)
    print("📊 PROCESSING SUMMARY")
    print("="*80)
    print(f"Total files:    {len(pdf_files)}")
    print(f"✅ Success:     {success}")
    print(f"⏭️  Skipped:     {skipped}")
    print(f"❌ Failed:      {failed}")
    if stopped > 0:
        print(f"⏸️  Not processed: {stopped}")
    print("="*80)
    print(f"\n✅ Outputs saved to:")
    print(f"   JSON: {json_dir}")
    print(f"   CSV:  {csv_dir}")
    print(f"   Logs: {log_dir}")
    print()


if __name__ == "__main__":
    main()
