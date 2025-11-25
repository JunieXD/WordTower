from app.db.question import random_select_question_type

if __name__ == "__main__":
    for i in range(70, 100):
        print(random_select_question_type(i))