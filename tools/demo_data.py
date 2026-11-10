# -*- coding: utf-8 -*-
"""通过接口在演示库中生成可见的留言、审核与标注数据。"""
import httpx

BASE = "http://127.0.0.1:8000/api/v1"

MESSAGES = [
    "请问图书馆今晚几点关门？想去看书。",
    "有没有人一起拼车去高铁站，周日下午三点出发。",
    "出一本高等数学教材，九成新，30 元，信息楼自取。",
    "三食堂新开的麻辣香锅味道不错，推荐给大家。",
    "求推荐适合新手的乒乓球拍，预算 200 左右。",
    "兼职刷单日赚三百，加微信 13800000000 详聊。",
    "低价代发各类广告，扫码进群领取名额。",
]


def login(client, username, password):
    r = client.post(f"{BASE}/auth/login", json={"username": username, "password": password})
    r.raise_for_status()
    data = r.json()["data"]
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]


with httpx.Client(timeout=20, trust_env=False) as client:
    student_headers, student = login(client, "student", "demo12345")
    admin_headers, admin = login(client, "admin", "demo12345")

    created = []
    for text in MESSAGES:
        r = client.post(f"{BASE}/messages", json={"content": text}, headers=student_headers)
        r.raise_for_status()
        data = r.json()["data"]
        created.append(data)
        print(f"publish id={data['id']} status={data['review_status']} "
              f"prediction={data['prediction_status']}")

    detail = client.get(f"{BASE}/classification/messages", headers=admin_headers,
                        params={"page": 1, "page_size": 50}).json()["data"]["list"]
    for item in detail[:7]:
        print("detail", item["id"], item["predicted_label"], item["predicted_probability"],
              item["review_status"], item["prediction_status"])

    pending = [m for m in created if m["review_status"] == "pending"]

    # 人工审核：第一条待审核留言通过，第二条驳回。
    if pending:
        first = pending[0]
        r = client.post(f"{BASE}/reviews/messages/{first['id']}",
                        json={"decision": "approved", "comment": "内容正常，予以通过"},
                        headers=admin_headers)
        print("approve", first["id"], r.status_code, r.json()["message"])
    if len(pending) > 1:
        second = pending[1]
        r = client.post(f"{BASE}/reviews/messages/{second['id']}",
                        json={"decision": "rejected", "comment": "广告引流内容，驳回"},
                        headers=admin_headers)
        print("reject", second["id"], r.status_code, r.json()["message"])

    # 人工标注：把第二条留言纠正为垃圾（演示人工纠正与历史记录）。
    target = created[1]["id"]
    r = client.post(f"{BASE}/classification/messages/{target}/annotations",
                    json={"label": "spam", "reason": "含推广引流话术，人工判为垃圾"},
                    headers=admin_headers)
    print("annotate", target, r.status_code, r.json()["message"])

    stats = client.get(f"{BASE}/statistics", headers=admin_headers).json()["data"]
    print("stats", stats)
    public = client.get(f"{BASE}/messages/public", headers=student_headers).json()["data"]
    print("public total", public["total"])
