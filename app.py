from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from sqlalchemy.orm import relationship
from flask import abort
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView

import os
import uuid



app = Flask(__name__)
app.secret_key = 'super_secret_1234'  # ← 適当に英数字でOK

# データベースの設定
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'app.db')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ✅ モデル定義（先に書く！）

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    posts = db.relationship('Post', backref='author', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
posts = db.relationship('Post', backref='author', lazy=True)



class Post(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    date = db.Column(db.Date)
    address = db.Column(db.String(200))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    map_iframe = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    photos = db.relationship('Photo', backref='post', cascade="all, delete", lazy=True)

class Photo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    photo_path = db.Column(db.String(200), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

# adminはモデル定義のあと！
admin = Admin(app, name='管理画面', template_mode='bootstrap3')

class UserAdmin(ModelView):
    column_list = ['id', 'username']
    form_excluded_columns = ['password_hash']

admin.add_view(UserAdmin(User, db.session))
admin.add_view(ModelView(Post, db.session))
admin.add_view(ModelView(Photo, db.session))

# ✅ サンプルデータ（プロフィール・学習ログ）
profile_info = {
    'name': '池田　大空',
    'age': 30,
    'skills': ['Python', 'JavaScript', 'HTML', 'CSS'],
}

learning_logs = [
    {'date': '2025-03-01', 'topic': 'Flask Basics', 'progress': 'Learned the basics of Flask and created a simple app.'},
    {'date': '2025-03-02', 'topic': 'CSS Styling', 'progress': 'Worked on styling my portfolio with CSS.'},
    {'date': '2025-03-03', 'topic': 'GitHub', 'progress': 'Started using GitHub for version control and pushing code.'},
]

# ✅ ルーティング

@app.route('/')
def home():
    posts = Post.query.order_by(Post.date.desc()).all()
    return render_template('index.html', posts=posts)
# ホームにアクセスしたら'index.html'を表示する　以下同義
@app.route('/profile')
def profile():
    return render_template('profile.html', profile=profile_info)

@app.route('/logs')
def logs():
    return render_template('logs.html', logs=learning_logs)

@app.route('/hiking')
def hiking():
    return render_template('hiking.html')

@app.route('/camping')
def camping():
    return render_template('camping.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # 同じユーザー名が登録済みかチェック
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return "このユーザー名はすでに使われています！"

        # 新規ユーザー作成
        new_user = User(username=username)
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))  # 登録後はログインページへリダイレクト

    return render_template('register.html')


# 入力(タイトルや日付)を受けて、データベースに保存する
@app.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        title = request.form['title']
        date_str = request.form['date']
        date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else None
        # 文字列を「年-月-日形式の日付オブジェクト」に変換してる
        #  Flaskでフォームから受けた日付”date”は文字列になる。
        # 　→しかしデータベースでは”Date型”として保存する。
        address = request.form['address']
        description = request.form['description']
        map_iframe = request.form.get('map_iframe')

        new_post = Post(
            title=title,
            date=date,
            address=address,
            description=description,
            map_iframe=map_iframe,
            user_id=current_user.id,  # ← 現在ログイン中のユーザーのIDを紐づける！
        )

        db.session.add(new_post)
        db.session.commit()

        # 写真アップロード処理
        if 'photos' in request.files:
            photos = request.files.getlist('photos')
            for photo in photos:
                if photo and photo.filename != '':
                    filename = str(uuid.uuid4()) + "_" + secure_filename(photo.filename)
                    filepath = os.path.join('static/uploads', filename)
                    photo.save(filepath)

                    new_photo = Photo(post_id=new_post.id, photo_path=filename)
                    db.session.add(new_photo)

            db.session.commit()

        return redirect(url_for('home'))

    return render_template('create.html')

@app.route('/post/<int:post_id>')
def post_detail(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template('post_detail.html', post=post)

@app.route('/edit/<int:post_id>', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    
    if post.user_id != current_user.id:
        abort(403)  # 権限がない場合は403エラー
        
    if request.method == 'POST':
        post.title = request.form['title']
        post.date = datetime.strptime(request.form['date'], "%Y-%m-%d").date() if request.form['date'] else None
        post.address = request.form['address']
        post.description = request.form['description']
        post.map_iframe = request.form.get('map_iframe')
        db.session.commit()
        return redirect(url_for('post_detail', post_id=post.id))
    
    return render_template('edit.html', post=post)

@app.route('/delete/<int:post_id>', methods=['POST', 'GET'])
@login_required
# セットで使うことで、ログインしてないとそもそもアクセスできなくなる
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    
    if post.user_id != current_user.id:
        abort(403)
    
    db.session.delete(post)
    db.session.commit()
    return redirect(url_for('home'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('home'))
        else:
            return "ログイン失敗！"

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))





# ✅ 最後に Flask アプリ起動。おまじないのようなもの
# 先にアプリの設定（最上部）やルート定義（ルーティング）が必要
if __name__ == '__main__':
    app.run(debug=True, port=5001)

# よくある構成
# 1. 必要なモジュールの import
# 2. app = Flask(__name__)
# 3. config（DB設定など）
# 4. db = SQLAlchemy(app)
# 5. モデル定義
# 6. ルーティング定義
# 7. 最後に app.run()
