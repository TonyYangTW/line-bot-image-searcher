#!/usr/bin/env python
# coding: utf-8

from flask import Flask
app = Flask(__name__)

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
import sqlite3
from config import client_id, line_channel_access_token, line_channel_secret
import pyimgur
try:
   import xml.etree.cElementTree as ET
except ImportError:
   import xml.etree.ElementTree as ET

#替換config.py中的token
line_bot_api = LineBotApi(line_channel_access_token)
handler = WebhookHandler(line_channel_secret)

#建立資料庫
conn = sqlite3.connect('line_bot_image_search.db')
c = conn.cursor()
c.execute("""CREATE TABLE if not exists "data" (
	"id"	INTEGER NOT NULL UNIQUE,
	"type"	TEXT NOT NULL,
	"state"	TEXT NOT NULL,
	"url"	TEXT NOT NULL,
	PRIMARY KEY("id")
)""")
conn.commit()


#建立路由
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

#針對加入群組的事件做處理
@handler.add(JoinEvent, )
def handle_join(event):
    print(event)
    conn = sqlite3.connect('line_bot_image_search.db')
    c = conn.cursor()
    res = "NULL"
    
    #判斷群組是否已存在資料庫中，以對資料庫進行資料的新增
    if event.source.type == "group":
        c.execute('SELECT id, type, state, url FROM data WHERE id=?', [event.source.group_id])
        cursor = c.fetchone()
        print(cursor)
        try:
            c.execute("INSERT INTO data (id, type, state, url) VALUES (?,?,?,?)", [event.source.group_id, "group", "activate", "no url"])
            res = "加入新群組!\n\n指令：\n!主動模式\n!被動模式\n!搜尋"
        except:
            res = "重新回到群組!\n\n指令：\n!主動模式\n!被動模式\n!搜尋"

    line_bot_api.reply_message(event.reply_token,TextSendMessage(text=res))

    conn.commit()
    conn.close()

#針對收到訊息的事件做處理
@handler.add(MessageEvent, message=(ImageMessage, TextMessage))
def handle_message(event):
    print(event)
    conn = sqlite3.connect('line_bot_image_search.db')
    c = conn.cursor()
    
    res = "NULL"
    if event.source.type == "group":
        c.execute('SELECT id, type, state, url FROM data WHERE id=?', [event.source.group_id])
        cursor = c.fetchone()

        #如果資料庫中沒有該群組的資料，新增一筆
        if cursor == None or cursor == []:
            try:                
                c.execute("INSERT INTO data (id, type, state, url) VALUES (?,?,?,?)", [event.source.group_id, "group", "activate", "no url"])
                c.execute('SELECT id, type, state, url FROM data WHERE id=?', [event.source.group_id])
                cursor = c.fetchone()
                print(cursor)
                conn.commit()
                res = "加入新群組!\n\n指令：\n!主動模式\n!被動模式\n!搜尋"
            except:
                res = "重新回到群組!\n\n指令：\n!主動模式\n!被動模式\n!搜尋"

        #針對接收到的文字指令切換模式與搜尋圖片
        if isinstance(event.message, TextMessage):
            mtext = event.message.text
            if mtext == "!主動模式":
                c.execute('UPDATE data SET state = "activate" WHERE id = ?', [event.source.group_id])
                res = "機器人已設為主動模式，將會為您搜尋接下來上傳的每張圖片"
            elif mtext == "!被動模式":
                c.execute('UPDATE data SET state = "passive" WHERE id = ?', [event.source.group_id])
                res = """機器人已設為被動模式，輸入"!搜尋"將會為您搜尋最後上傳的圖片"""
            elif mtext == "!搜尋":
                if cursor[3] == "no url":
                    res = "群組中沒有上傳過圖片，或是圖片是在機器人加入前上傳的\n請再試一次！"
                else:
                    url = "https://www.google.com/searchbyimage?&image_url=" + cursor[3]
                    res = "已為您上傳並搜尋群組中最後一張圖片\n以下為本次的搜尋結果\n" + url + \
                            "\n\n若想檢視原始圖片，請點擊下列網址\n" + cursor[3]
                
    #針對接收到的圖片做處理           
    if isinstance(event.message, ImageMessage):
        #取得圖片並建立站存檔
        message_content = line_bot_api.get_message_content(event.message.id)
        file_path = "/tmp/" + event.message.id + ".jpg"
        with open(file_path, 'wb') as tf:
            for chunk in message_content.iter_content():
                tf.write(chunk)

        print(file_path)
       
        #設定Imgur api所需的資訊
        CLIENT_ID = client_id
        PATH = file_path #A Filepath to an image on your computer"
        title = "Uploaded with PyImgur"

        #透過Imgur api上傳圖片
        im = pyimgur.Imgur(CLIENT_ID)
        uploaded_image = im.upload_image(PATH, title=title)

        #透過google search by image api取得結果，判斷群組所設定的模式以設定訊息
        url = "https://www.google.com/searchbyimage?&image_url=" + uploaded_image.link_big_square
        if event.source.type == "group" and cursor[2] == "passive":
            c.execute('UPDATE data SET url = ? where id = ?', [uploaded_image.link, event.source.group_id])
            print("passive")
        elif event.source.type == "group" and cursor[2] == "activate":
            c.execute('UPDATE data SET url = ? where id = ?', [uploaded_image.link, event.source.group_id])
            print("activate")
            res = "已為您上傳並搜尋圖片\n以下為本次的搜尋結果\n" + url + \
                "\n\n若想檢視原始圖片，請點擊下列網址\n" + uploaded_image.link
        else:
            res = "已為您上傳並搜尋圖片\n以下為本次的搜尋結果\n" + url + \
                "\n\n若想檢視原始圖片，請點擊下列網址\n" + uploaded_image.link
    
    if res != "NULL":
        line_bot_api.reply_message(event.reply_token,TextSendMessage(text=res))

    conn.commit()
    conn.close()

   
if __name__ == '__main__':
    app.run()
