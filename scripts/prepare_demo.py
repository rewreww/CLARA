"""Create local deployment secrets once. Never print credentials to logs."""
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
folder = root / '.clara' / 'deployment'
folder.mkdir(parents=True, exist_ok=True)
gateway = folder / 'gateway.env'
vercel = folder / 'vercel.env'
if gateway.exists() or vercel.exists():
    if not (gateway.exists() and vercel.exists()):
        raise SystemExit('Only one secret file exists. Restore the matching file; no values were changed.')
    print('Existing deployment credentials preserved in .clara/deployment/.')
else:
    key = secrets.token_urlsafe(48)
    password = secrets.token_urlsafe(18)
    gateway.write_text(f'CLARA_GATEWAY_KEY={key}\n', encoding='utf-8')
    vercel.write_text('CLARA_DEMO_ENABLED=true\nVITE_RESPONDENT_DEMO=true\nCLARA_DEMO_USERNAME=respondent\n'
        f'CLARA_DEMO_PASSWORD={password}\nCLARA_GATEWAY_KEY={key}\n'
        'CLARA_GATEWAY_URL=https://REPLACE-WITH-YOUR-NGROK-DOMAIN\n', encoding='utf-8')
    print('Created private deployment files in .clara/deployment/. Do not commit or share these files.')
