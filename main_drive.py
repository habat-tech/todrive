import os
import logging
import tempfile
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

# إعداد السجل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# مسار حفظ ملف بيانات الاعتماد الدائم
CREDENTIALS_PATH = "drive_credentials.json"
# مسار ملف بيانات الاعتماد PyDrive
PYDRIVE_CREDS_PATH = "credentials.json"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "مرحباً! أرسل لي فيديو (أو ملف فيديو) للرفع إلى Google Drive.\n"
        "إذا أردت رفع ملف بيانات الاعتماد (JSON) استخدم الأمر /uplode_json."
    )

async def uplode_json_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("الرجاء إرسال ملف JSON (بيانات اعتماد Google Drive) الآن.")

async def handle_json_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document or not document.file_name.lower().endswith('.json'):
        # ليس ملف JSON، نمرره إلى معالج الفيديو
        await handle_video(update, context)
        return
        
    file_id = document.file_id
    new_file = await context.bot.get_file(file_id)
    try:
        await new_file.download_to_drive(custom_path=CREDENTIALS_PATH)
        await update.message.reply_text("تم رفع ملف JSON وحفظه بنجاح!")
        logger.info("تم حفظ ملف بيانات الاعتماد في %s", CREDENTIALS_PATH)
    except Exception as e:
        logger.error("خطأ أثناء حفظ ملف JSON: %s", e)
        await update.message.reply_text(f"حدث خطأ أثناء رفع الملف: {e}")

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    # تجاهل الرسائل بدون ملفات
    if not (message.video or message.document):
        return

    # إذا كان ملف JSON، فتأكد من أنه تم التعامل معه في معالج JSON
    if message.document and message.document.file_name.lower().endswith('.json'):
        return

    video = message.video or message.document
    file_id = video.file_id
    new_file = await context.bot.get_file(file_id)
    
    # تنزيل الملف إلى ملف مؤقت
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    temp_file.close()
    await new_file.download_to_drive(custom_path=temp_file.name)
    await message.reply_text("تم تنزيل الفيديو، جاري رفعه إلى Google Drive...")

    try:
        # إعداد PyDrive باستخدام OAuth2 بدلاً من ServiceAuth
        gauth = GoogleAuth()
        gauth.settings['client_config_file'] = CREDENTIALS_PATH
        
        # تحقق إذا كانت هناك بيانات اعتماد مخزنة مسبقاً
        if os.path.exists(PYDRIVE_CREDS_PATH):
            gauth.LoadCredentialsFile(PYDRIVE_CREDS_PATH)
            
        if gauth.credentials is None:
            # إذا لم تكن هناك بيانات اعتماد صالحة، استخدم LocalWebserverAuth
            gauth.LocalWebserverAuth()
        elif gauth.access_token_expired:
            # إذا انتهت صلاحية الرمز المميز، قم بتحديثه
            gauth.Refresh()
        else:
            # تهيئة بيانات الاعتماد الحالية
            gauth.Authorize()
            
        # حفظ بيانات الاعتماد للاستخدام المستقبلي
        gauth.SaveCredentialsFile(PYDRIVE_CREDS_PATH)
        
        drive = GoogleDrive(gauth)

        # إنشاء ملف على Google Drive ورفعه
        file_title = os.path.basename(temp_file.name)
        file_drive = drive.CreateFile({'title': file_title})
        file_drive.SetContentFile(temp_file.name)
        file_drive.Upload()
        await message.reply_text("تم رفع الفيديو بنجاح إلى Google Drive!")
    except Exception as e:
        logger.error("خطأ أثناء رفع الملف إلى Drive: %s", e)
        await message.reply_text(f"حدث خطأ أثناء رفع الفيديو: {e}")
    finally:
        os.remove(temp_file.name)

def main():
    # استخدم التوكن المقدم
    token = "8134559871:AAF2O5jkNzTeTlIQXsm3ABsdWTkf-Y7OIT0"
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("uplode_json", uplode_json_command))
    
    # تعامل مع الوثائق 
    app.add_handler(MessageHandler(filters.Document.ALL, handle_json_upload))
    
    # تعامل مع ملفات الفيديو
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))

    logger.info("البوت يعمل الآن...")
    app.run_polling()

if __name__ == '__main__':
    main()