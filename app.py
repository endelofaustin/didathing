import shelve
from flask import Flask, render_template, request

app = Flask(__name__)

@app.route('/')
def hello():
    return render_template('index.html')

@app.route('/create_list', methods=['POST'])
def create_list():
    list_name = request.form['list_name']
    new_list = []

    # Store the new list in the database
    with shelve.open('lists.db') as db:
        db[list_name] = new_list

    return f'Python list named "{list_name}" created: {new_list}'

@app.route('/add_item', methods=['POST'])
def add_item():
    list_name = request.form['list_name']
    item_name = request.form['item_name']

    # Get the existing list from the database, or create a new one if it doesn't exist
    with shelve.open('lists.db', writeback=True) as db:
        existing_list = db.get(list_name, [])
        existing_list.append(item_name)
        db[list_name] = existing_list

    return f'Item "{item_name}" added to the list "{list_name}"'

@app.route('/lists')
def show_lists():
    # Fetch all lists from the database and display them
    with shelve.open('lists.db') as db:
        all_lists = [(name, db[name]) for name in db.keys()]

    return render_template('lists.html', all_lists=all_lists)

if __name__ == '__main__':
    app.run(debug=True)

