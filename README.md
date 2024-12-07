Проект по курсу "Язык программирования Python (углубленный курс)". Авторы: Сергиенко Елизавета и Дубровин Александр, студенты 3 курса ОП "Экономика и статистика" НИУ ВШЭ

## Схема проекта

![Schema](telemail_schema.png)

## Описание

Функционал проекта:
Телеграм-бот, который будет присылать пользователю уведомления о получении сообщений на электронный почтовый ящик с указанием их важности/тематики/статуса отправителя и др. параметров, настраиваемых пользователем. 

Примерный сценарий взаимодействия с пользователем:
В самом начале наш  User заходит в  Telegram App. Наш Telegram bot взаимодействует с  Telegram App через Telegram API. Пользователь через веб-интерфейс указывает свой почтовый ящик и настраивает параметры парсинга через создание системы ключевых слов (будем называть хештегами), указание категорий отправителей, почтовый сервер отправленного письма
После введенных параметров, система начинает анализировать приходящие письма по структуре: Имя отправителя -> Дедлайн ответа -> Указанные в письме места -> Категория письма -> Статус (Срочное, несрочное) -> и др. (в процессе разработки необходимо доопределить!)
Далее пользователь получает уведомления о входящих письмах. Вполне возможно настроить сводку по почтовому ящику посуточную/почасовую с информацией по типу "Хозяин, вашего ответа ждут 3 новых письма в 
категориях ...". Соответственно, здесь может быть настроена почтовая история.

Начинка и внутренняя работа системы:
Для взаимодействия с API Telegram мы будем использовать aiogram. С помощью aiogram можно отправлять и получать сообщения, управлять чатами, обрабатывать команды пользователей и многое другое. Итоговую программу разобьем на 2 части: 
‘Telegram Bot’ 
‘Mails and auth data processing’, которая будет отвечать за парсинг почты, работу с провайдером аутентификации (Google, VkID) и работу с БД.
 
В блоке ‘Mails and auth data processing’ мы будем использовать следующие библиотеки:
fastapi - асинхронный веб-фреймворк, который мы будем использовать для получения токенов авторизации от Google.
oauthlib - для работы с протоколом oauth2(нужно для получения авторизационных токенов). В свою очередь токены нам понадобятся для взаимодействия с GoogleAPI,  получения почты и информации о пользователе.
pika -  для взаимодействия с RabbitMQ - это популярный брокер сообщений, который используется для обработки и маршрутизации сообщений между различными компонентами распределенных приложений. А с RabbitMq мы будем работать через библиотеку pika.
asyncpg - для работы с Postgresql. 
sqlite3 - для работы с встраиваемой БД sqlite
Взаимодействие между ‘Telegram Bot’ и ‘Mails and auth data processing’ будет происходить с помощью RabbitMQ.

## Ход работы
1. Зарегистрировали приложение в аккаунте Google for developers
2.  Зарегистрировали домен для приложения: `tlm.tmhu.space`
3. Развернули nginx для проксирования запросов к FastAPI:
```nginx
upstream telemail {  
       server 127.0.0.1:5000;  
}

server {  
   server_name tlm.tmhu.space www.tlm.tmhu.space;  
      
   access_log /var/log/nginx/telemail.access.log;  
   error_log /var/log/nginx/telemail.error.log;  
   
   location / {  
       proxy_pass https://telemail;  
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;  
       proxy_set_header X-Real-IP $remote_addr;  
       proxy_set_header Host $http_host;  
       proxy_http_version 1.1;  
       proxy_redirect off;  
       proxy_buffering off;  
       proxy_set_header Upgrade $http_upgrade;  
       proxy_set_header Connection "upgrade";  
       proxy_read_timeout 86400;  
   }  
  
   listen 443 ssl; # managed by Certbot  
   ssl_certificate /etc/letsencrypt/live/tlm.tmhu.space/fullchain.pem; # managed by Certbot  
   ssl_certificate_key /etc/letsencrypt/live/tlm.tmhu.space/privkey.pem; # managed by Certbot  
   include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot  
   ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; # managed by Certbot  
  
  
}  
server {  
   if ($host = tlm.tmhu.space) {  
       return 301 https://$host$request_uri;  
   } # managed by Certbot  
  
  
   listen 80;  
   server_name tlm.tmhu.space www.tlm.tmhu.space;  
   return 404; # managed by Certbot  
}
```
4. Развернули RabbitMQ.
5. Написали в тестовом режиме базовый функционал:
        1. Приветственное сообщение в телеграм;
        2. Генерацию ссылки для Oauth2-авторизации в Google.
        3. При авторизации запрашиваются следующие права:
                1. Получение openid.
                2. Получение информации о профиле пользователя.
                3. Получение информации о почте пользователя.
                4. Получение права на чтение почты пользователя.
                5. Получение метаданных о почтовом ящике пользователя.
        4. После авторизации пользователя приложение на FastAPI получает токен, дающий перечисленные выше права, получает общую информацию о пользователе и посылает через RabbitMQ боту сообщение пользователю об успешной регистрации.

