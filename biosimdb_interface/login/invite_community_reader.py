import os
import requests
user_id = "ADD ID"
slug = "biosimdb"
base = "https://data-collections-dev.psdi.ac.uk"
token = "ADD TOKEN"
headers = {"Authorization": "Bearer " + token}
r = requests.get(base + "/api/communities/" + slug, headers=headers)
community_id = r.json()["id"]
r = requests.get(base + "/api/communities/" + community_id + "/members", params={"size": 1000}, headers=headers)
found = False
for m in r.json()["hits"]["hits"]:
   if m["member"]["id"] == user_id:
       found = True
if found:
   print("member of " + slug)
else:
   data = {"members": [{"id": user_id, "type": "user"}], "role": "reader"}
   requests.post(base + "/api/communities/" + community_id + "/invitations", json=data, headers=headers)
   print("invited user " + user_id + " to " + slug)