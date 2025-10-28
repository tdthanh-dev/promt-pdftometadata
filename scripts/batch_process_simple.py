"""
Simple batch processor using main.py logic.
Processes all PDF files in a directory.
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
    log_file = log_dir / f"batch_{timestamp}.log"
    
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
    """Batch process PDFs in data/raw_pdfs/THONGBAO/"""
    
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
    
    logger.info("="*80)
    logger.info(f"🚀 BATCH PROCESSING - {len(pdf_files)} files")
    logger.info("="*80)
    logger.info(f"Input:  {input_dir}")
    logger.info(f"Output: json={json_dir}, csv={csv_dir}")
    logger.info("="*80)
    
    # Stats
    success = 0
    failed = 0
    skipped = 0
    
    # Process each file
    for idx, pdf_path in enumerate(pdf_files, 1):
        file_name = pdf_path.stem
        json_output = json_dir / f"{file_name}_output.json"
        
        # Skip if exists
        if json_output.exists():
            logger.info(f"[{idx}/{len(pdf_files)}] ⏭️  SKIP: {pdf_path.name} (exists)")
            skipped += 1
            continue
        
        logger.info(f"\n[{idx}/{len(pdf_files)}] 🔄 Processing: {pdf_path.name}")
        
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
                
                # Move CSVs
                src_doc_csv = Path(f"{file_name}_document.csv")
                src_chunks_csv = Path(f"{file_name}_chunks.csv")
                
                if src_doc_csv.exists():
                    shutil.move(str(src_doc_csv), str(csv_dir / src_doc_csv.name))
                
                if src_chunks_csv.exists():
                    shutil.move(str(src_chunks_csv), str(csv_dir / src_chunks_csv.name))
                
                success += 1
                logger.info(f"✅ SUCCESS: {pdf_path.name}")
            else:
                failed += 1
                logger.error(f"❌ FAILED: {pdf_path.name} - No result")
        
        except Exception as e:
            failed += 1
            logger.error(f"❌ ERROR: {pdf_path.name} - {e}")
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("📊 SUMMARY")
    logger.info("="*80)
    logger.info(f"Total:    {len(pdf_files)}")
    logger.info(f"✅ Success: {success}")
    logger.info(f"⏭️  Skipped: {skipped}")
    logger.info(f"❌ Failed:  {failed}")
    logger.info("="*80)


if __name__ == "__main__":
    main()
