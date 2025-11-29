from PyPDF2 import PdfMerger

# إنشاء كائن الدمج
merger = PdfMerger()

# سؤال المستخدم عن عدد الملفات
# int() تقوم بتحويل النص الذي يدخله المستخدم إلى رقم
try:
    file_count = int(input("How many PDF files do you want to merge? "))
except ValueError:
    print("Error: Please enter a valid number.")
    exit() # الخروج من البرنامج إذا لم يدخل المستخدم رقماً

# حلقة (loop) لتكرار سؤال المستخدم عن اسم كل ملف
for i in range(file_count):
    # str(i + 1) لجعل السؤال يبدو هكذا: "Enter name of file 1: "
    file_name = input("Enter name of file " + str(i + 1) + " (with .pdf): ")
    
    try:
        # محاولة إضافة الملف إلى قائمة الدمج
        merger.append(file_name)
        print(f"Added '{file_name}' successfully.")
    except FileNotFoundError:
        # إذا لم يتم العثور على الملف، اطبع رسالة خطأ واخرج
        print(f"Error: The file '{file_name}' was not found. Please check the name and try again.")
        merger.close()
        exit()

# سؤال المستخدم عن اسم الملف النهائي
output_name = input("What do you want to name the final merged file? (with .pdf): ")

# كتابة النتيجة النهائية
merger.write(output_name)
merger.close()

# طباعة رسالة النجاح النهائية
print(f"\nSuccess! All files have been merged into '{output_name}'")

