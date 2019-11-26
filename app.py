from flask import Flask, request, jsonify, render_template
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
from bson.json_util import dumps
from bson.objectid import ObjectId

app = Flask(__name__)

url_db = "mongodb://<username>:<password>@ds041111.mlab.com:41111/<database>"

bcrypt = Bcrypt()


def create_connection(url):
    return MongoClient(url, retryWrites=False)


def valid_password(name, password):
    with create_connection(url_db) as connection:
        db = connection["flask_task"]
        posts = db.users
        user_data = posts.find_one({'username': name})
        if user_data:
            if bcrypt.check_password_hash(user_data['password'], password):
                return True
            else:
                return False
        else:
            return False


@app.route('/api/voting/', methods=['POST', 'GET'])
def voting():
    if request.method == 'POST':
        auth = request.authorization
        if valid_password(auth.username, auth.password):
            content = request.get_json()
            if len(content['answers']) < 2:
                return 'Must be at least 2 answers'
            content['author'] = auth.username
            i = 1
            for d in content['answers']:
                d['id'] = i
                d['voted'] = []
                i += 1
            content['max_id'] = i
            with create_connection(url_db) as connection:
                db = connection["flask_task"]
                posts = db.voting
                posts.insert_one(content)
            return 'Voting successfully added'
        else:
            return 'You do not have an access. Incorrect login or password.'
    else:
        with create_connection(url_db) as connection:
            db = connection["flask_task"]
            vote_collection = db['voting']
            json_coll = vote_collection.find()
            json_list = []
            for d in vote_collection.find():
                for answ in d['answers']:
                    answ.pop('voted')
                d.pop('max_id')
                json_list.append(d)
            return dumps(json_list)


@app.route('/api/voting/<voting_id>/', methods=['POST', 'GET', 'DELETE'])
def change_voting(voting_id):
    voting_id = ObjectId(voting_id)
    if request.method == 'POST':
        auth = request.authorization
        if valid_password(auth.username, auth.password):
            content = request.get_json()
            with create_connection(url_db) as connection:
                db = connection["flask_task"]
                vote_collection = db['voting']
                post = vote_collection.find_one({'_id': voting_id})
                if post:
                    if post['author'] == auth.username:
                        i = post['max_id']
                        for answ in content['answers']:
                            if 'id' in answ:
                                for doc_answ in post['answers']:
                                    if doc_answ['id'] == answ['id']:
                                        doc_answ['text'] = answ['text']
                                        break
                            else:
                                answ['id'] = i
                                answ['voted'] = []
                                i += 1
                                post['answers'].append(answ)
                        post['max_id'] = i
                        vote_collection.update_one({'_id': voting_id},
                                                   {"$set": post})
                        return 'Voting was successfully updated'
                    else:
                        return '''Access denied.
                        This voting was created by other author'''
                else:
                    return 'There is no voting with that _id'
        else:
            return 'You do not have an access. Incorrect login or password.'
    elif request.method == 'DELETE':
        auth = request.authorization
        if valid_password(auth.username, auth.password):
            with create_connection(url_db) as connection:
                db = connection["flask_task"]
                vote_collection = db['voting']
                post = vote_collection.find_one({'_id': voting_id})
                if post:
                    if post['author'] == auth.username:
                        vote_collection.delete_one({'_id': voting_id})
                        return 'Voting has been deleted successfully'
                    else:
                        return '''Access denied.
                        This voting was created by other author'''
                else:
                    return 'There is no voting with that _id'
        else:
            return 'You do not have an access. Incorrect login or password.'
    else:
        auth = request.authorization
        with create_connection(url_db) as connection:
            db = connection["flask_task"]
            vote_collection = db['voting']
            post = vote_collection.find_one({'_id': voting_id})
            if post:
                post.pop('max_id')
                if auth:
                    isVoted = False
                    num_vote = 0
                    for answ in post['answers']:
                        if auth.username in answ['voted']:
                            isVoted = True
                            post['user_vote'] = answ['id']
                        num_vote += len(answ['voted'])
                    if isVoted:
                        for answ in post['answers']:
                            answ['percentage'] = (len(answ['voted']) /
                                                  num_vote * 100)
                            answ.pop('voted')
                        post['num_vote'] = num_vote
                        return dumps(post)
                    else:
                        for answ in post['answers']:
                            answ.pop('voted')
                        return dumps(post)
                else:
                    for answ in post['answers']:
                        answ.pop('voted')
                    return dumps(post)
            else:
                return 'There is no voting with that _id'


@app.route('/api/voting/<voting_id>/<answer_id>',
           methods=['POST', 'GET', 'DELETE'])
def make_vote(voting_id, answer_id):
    voting_id = ObjectId(voting_id)
    answer_id = int(answer_id)
    if request.method == 'POST':
        auth = request.authorization
        if valid_password(auth.username, auth.password):
            with create_connection(url_db) as connection:
                db = connection["flask_task"]
                vote_collection = db['voting']
                post = vote_collection.find_one({'_id': voting_id})
                if post:
                    isCorrect = False
                    for answ in post['answers']:
                        if answ['id'] == answer_id:
                            isCorrect = True
                    if isCorrect:
                        for answ in post['answers']:
                            if auth.username in answ['voted']:
                                if answ['id'] == answer_id:
                                    return '''You have already
                                    voted for this answer'''
                                else:
                                    answ['voted'].remove(auth.username)
                            elif answ['id'] == answer_id:
                                answ['voted'].append(auth.username)
                        vote_collection.update_one({'_id': voting_id},
                                                   {"$set": post})
                        return 'Your vote has been successfully counted'
                    else:
                        return 'There is no answer with that id'
                else:
                    return 'There is no voting with that _id'
        else:
            return 'You do not have an access. Incorrect login or password.'
    elif request.method == 'DELETE':
        auth = request.authorization
        if valid_password(auth.username, auth.password):
            with create_connection(url_db) as connection:
                db = connection["flask_task"]
                vote_collection = db['voting']
                post = vote_collection.find_one({'_id': voting_id})
                if post:
                    if post['author'] == auth.username:
                        for answ in post['answers']:
                            if answ['id'] == answer_id:
                                if len(post['answers']) <= 2:
                                    return '''You can not delete that answer.
                                    Must be at least 2 answers'''
                                else:
                                    post['answers'].remove(answ)
                                    vote_collection.update_one({'_id': voting_id},
                                                               {"$set": post})
                                    return '''The answer has been
                                    deleted successfully'''
                        return 'There is no answer with that id'
                    else:
                        return '''Access denied. This voting was created
                        by other author'''
                else:
                    return 'There is no voting with that _id'
        else:
            return 'You do not have an access. Incorrect login or password.'
    else:
        auth = request.authorization
        with create_connection(url_db) as connection:
            db = connection["flask_task"]
            vote_collection = db['voting']
            post = vote_collection.find_one({'_id': voting_id})
            if post:
                for answ in post['answers']:
                    if answer_id == answ['id']:
                        answ.pop('voted')
                        return dumps(answ)
                return 'There is no answer with that id'
            else:
                return 'There is no voting with that _id'


@app.route('/api/signUp', methods=['POST', 'GET'])
def signup():
    if request.method == 'POST':
        auth = request.authorization
        if not auth:
            return 'Insert login and password in post-request form auth='
        with create_connection(url_db) as connection:
            db = connection["flask_task"]
            posts = db.users
            if not posts.find_one({'username': auth.username}):
                post = {'username': auth.username,
                        'password': bcrypt.generate_password_hash(auth.password).decode('utf-8')}
                posts.insert_one(post)
            else:
                return 'User with this name already registred'
            return 'User successfully added'
    return 'Insert login and password in post-request form auth='


@app.route('/')
def starter():
    return render_template('home.html')

if __name__ == "__main__":
    app.run()
