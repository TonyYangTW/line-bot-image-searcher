# line-bot-image-searcher
這是一個幫助您在使用Line時，如果遇到不清楚來源的圖片，或是對於圖片上所傳達的資訊有所疑慮時，可以快速搜尋圖源的工具

* 提供個人聊天室即時查詢的功能

* 以及群組中兩種模式的回應方案

* 可透過以下 QR Code 將機器人設為好友

![GITHUB](https://i.imgur.com/nr1gGN1.jpg "QR Code")

## 建構過程

首先要先進行 api key 的設定

### config.py
將 config.py 中的 line_channel_access_token 及 line_channel_secret 替換為自己的

如還未建立使用 Messaging API 的 Line 機器人，可以參考以下[LINE Developers官方指引頁面](https://developers.line.biz/en/docs/messaging-api/getting-started/)

而 imgur key 的部分，首先前往 [Imgur](imgur.com/register) 建立一個帳戶，完成後前往 [Register your application](https://api.imgur.com/oauth2/addclient) 申請並替換 config.py 中的 client_id

### 代理伺服器
因 LINE Bot 使用 webhook url 做為伺服器連結，而 webhook url 要求必須是 https 通訊協定的網址，所以我們勢必要有一個代理伺服器

本篇範例是透過heroku進行代理，首先要先安裝 gunicorn

    – pip install gunicorn

安裝完成後前往[Heroku Dev Center](https://devcenter.heroku.com/)註冊帳號，並根據作業系統版本下載 Heroku CLI

> #### 登入並建立應用程式

    – heroku login
    – heroku create {appname} #若出現 ! Name is already taken的警告訊息，代表此app名字已被別人使用，換個名字即可


而除了程式檔外所必要的 **requirements.txt** 以及 **Procfile** 都包含在本專案中，與專案放在同一個資料夾，其功能為告訴 Heroku 本專案所需要的套件以及如何啟動

> #### 將本專案推至 Heroku

    - git init
    - heroku git:remote -a {appname}
    - git add .
    - git commit -am "{填寫版本資訊}"

更多詳情可以參考[heroku官方指引頁面](https://devcenter.heroku.com/articles/getting-started-with-python)

部屬完成後會得到代理網址，將網址加上 "/callback" 後貼至 [LINE Developers Consloe](https://developers.line.biz/console/) > 你的專案 > Messaging API > Webhook settings > Webhook URL 中，至此完成建構的步驟。

![GITHUB](https://i.imgur.com/4DxUYBo.jpg "Webhook URL")

## 介紹
此程式旨在提供一個簡單易用且快速的方式對 Line 聊天室收到的圖片進行搜尋，不論在任何聊天室收到圖片，只要一鍵轉發給本機器人，就可以快速收到結果，省去下載或開啟其他應用程式的過程，並且附帶將圖片上傳圖床的功能

此外，本程式支援加入群組，對於近期流竄於各個 Line 群組的不實圖片，也可以及時搜尋其出處

並且因群組可能人數或訊息眾多，過多圖片的傳送可能導致機器人必須一直回傳結果造成困擾

所以本程式透過 SQLite 建立資料庫儲存個個群組的設定，為群組提供每張圖片都會回傳搜尋結果的 **"主動模式"** 以及只有在收到特定指令時才會回傳群組中最後一張圖片的搜尋結果的 **"被動模式"**

## 實作細節
因 google 圖片搜尋 api 需要有圖片實體的網址，需要先將圖片上傳至圖床，本程式以 Imgur 為例

> 首先與 Line Messaging API 建立路由
```python
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'
```

> 收到圖片訊息後將圖片暫存
```python
if isinstance(event.message, ImageMessage):
        #取得圖片並建立站存檔
        message_content = line_bot_api.get_message_content(event.message.id)
        file_path = "/tmp/" + event.message.id + ".jpg"
        with open(file_path, 'wb') as tf:
            for chunk in message_content.iter_content():
                tf.write(chunk)
```

> 透過 Imgur API 上傳圖片，並經由 Google search by image api 取得結果

```python
CLIENT_ID = client_id
        PATH = file_path #A Filepath to an image on your computer"
        title = "Uploaded with PyImgur"

        #透過Imgur api上傳圖片
        im = pyimgur.Imgur(CLIENT_ID)
        uploaded_image = im.upload_image(PATH, title=title)

        #透過google search by image api取得結果，判斷群組所設定的模式以設定訊息
        url = "https://www.google.com/searchbyimage?&image_url=" + uploaded_image.link_big_square
```

### 群組部分
首先為了能夠加入群組，先至 [LINE Developers Consloe](https://developers.line.biz/console/) > 你的專案 > Messaging API > LINE Official Account features > Allow bot to join group chats > Edit 將選項設為 Enabled

為了提供兩種模式，選擇使用 SQLite3 建立資料庫存放存組 ID, 設定, 最後上傳的圖片等

> 建立資料庫
```python
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
```

> 將加入的新群組新增在資料庫中
```python
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
```

> 針對接收到的文字指令切換模式與搜尋圖片
```python
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
```

## 結果
* 個人聊天室

> ![GITHUB](https://i.imgur.com/LXq8HqO.jpg, "結果_1")

* 加入群組

> ![GITHUB](https://i.imgur.com/emQD7qJ.jpg, "結果_2")

* 主動模式

> ![GITHUB](https://i.imgur.com/xooxspH.jpg, "結果_3")

* 被動模式

> ![GITHUB](https://i.imgur.com/XUkEprH.jpg, "結果_4")

## 參考
* LINE Messaging API：[https://developers.line.biz/en/docs/messaging-api/getting-started/](https://developers.line.biz/en/docs/messaging-api/getting-started/)
* Imgur API：[https://api.imgur.com/](https://api.imgur.com/)
* Heroku：[https://devcenter.heroku.com/articles/getting-started-with-python](https://devcenter.heroku.com/articles/getting-started-with-python)
* SQLite：[https://www.sqlitetutorial.net/](https://www.sqlitetutorial.net/)
