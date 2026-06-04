from pathlib import Path
from datetime import datetime
import shutil
src=Path('instance/solar_documents.db')
out=Path('backups'); out.mkdir(exist_ok=True)
if not src.exists(): print('Database not found:', src)
else:
    dst=out/f'solar_documents_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
    shutil.copy2(src,dst); print('Backup created:', dst)
