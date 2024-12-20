import os
from flask import Flask, request, redirect, jsonify, render_template
from flask_caching import Cache
from flask_limiter import Limiter
from flask_sqlalchemy import SQLAlchemy
from flask_limiter.util import get_remote_address
import shortuuid
import psycopg2


db = SQLAlchemy()

app = Flask(__name__)

app.secret_key = os.environ.get('FLASK_SECRET_KEY')
user_db = "postgres"
host_ip = "127.0.0.1"
host_port = "5432"
database_name = "rpp_flask"

app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{user_db}:@{host_ip}:{host_port}/{database_name}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['CACHE_TYPE'] = 'simple'
app.config['CACHE_DEFAULT_TIMEOUT'] = 3600

db.init_app(app)

cache = Cache(app)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["100/day"]
)

class UrlDb(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_url = db.Column(db.String(5000), nullable=False, unique=True)
    short_id = db.Column(db.String(5000), nullable=False, unique=True)
    user_id = db.Column(db.String(5000), nullable=False)
    clicks = db.Column(db.Integer, default=0)  
    ip_addresses = db.Column(db.Text) 


    def __repr__(self):
        return f'id:{self.id}, original_url:{self.original_url}, short_id:{self.short_id}, user_id:{self.user_id}, clicks:{self.clicks}, ip_addresses:{self.ip_addresses}'


@app.route('/shorten', methods=['GET', 'POST'])
@limiter.limit("10/day", error_message="В день доступно только 10 запросов. Попробуйте завтра.")
def shorten_url():
    original_url = request.form.get('originalUrl')
    user_id = request.form.get('userId')
    error_message = None
    short_url = None

    if not original_url:
        error_message = "Введите ссылку"

    else:
        short_id = shortuuid.uuid()[:6]
        existing_url = UrlDb.query.filter_by(original_url=original_url).first()
        if existing_url:
            short_url = existing_url.short_id
        else:
            newURL = UrlDb(original_url=original_url, short_id=short_id, user_id=user_id)
            db.session.add(newURL)
            db.session.commit()

    return render_template('index.html', short_url=short_url, error_message=error_message)



@app.route('/<short_id_1>')
@limiter.limit("100/day", error_message="В день доступно только 100 кликов по ссылке. Попробуйте завтра.")
def redirect_to_url(short_id_1):
    url = UrlDb.query.filter_by(short_id=short_id_1).first()
    cached_url = cache.get(short_id_1)
    if cached_url:
        url.clicks += 1
        db.session.commit() 
        return redirect(cached_url)

   

    ip_address = request.remote_addr

    ip_addresses = url.ip_addresses if url.ip_addresses else ""
    if ip_address not in ip_addresses.split(','):
        ip_addresses += ',' + ip_address if ip_addresses else ip_address
        url.ip_addresses = ip_addresses

    url.clicks += 1
    db.session.commit() 
    cache.set(short_id_1, url.original_url)
    
    return redirect(url.original_url)
    


@app.route('/stats/<short_id>')
def get_stats(short_id):
    url = UrlDb.query.filter_by(short_id=short_id).first()
    if not url:
        return render_template('stats.html', error='Такой короткой ссылки не существует')
    return render_template('stats.html', short_id=short_id, clicks=url.clicks, ip_addresses=url.ip_addresses)



if __name__ == '__main__':
    app.run(debug=True)