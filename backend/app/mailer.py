"""Optional SMTP notifications. Missing configuration disables delivery safely."""
import os
import smtplib
from email.message import EmailMessage

def send_alert_email(title: str, detail: str) -> bool:
    host, user, password, recipient = (os.getenv(k,'') for k in ('SMTP_HOST','SMTP_USER','SMTP_PASSWORD','ALERT_TO_EMAIL'))
    if not all((host,user,password,recipient)): return False
    msg = EmailMessage(); msg['Subject'] = '[ProfitLens] '+title
    msg['From'] = os.getenv('SMTP_FROM',user); msg['To']=recipient
    msg.set_content(f'{title}\n\n{detail}\n\nOpen your ProfitLens dashboard to investigate.')
    port = int(os.getenv('SMTP_PORT','587'))
    try:
        if port==465:
            with smtplib.SMTP_SSL(host,port,timeout=15) as client:
                client.login(user,password);client.send_message(msg)
        else:
            with smtplib.SMTP(host,port,timeout=15) as client:
                client.starttls();client.login(user,password);client.send_message(msg)
        return True
    except (OSError, smtplib.SMTPException) as e:
        print(f'SMTP delivery failed: {type(e).__name__}')
        return False
