# Notifications — hagaajinta iyo rakibidda

Taariikh: 14 Sebtembar 2026

## Waxa la saxay

- Qofka fariinta loogu talagalay wuxuu leeyahay inbox u gaar ah. Account kasta
  oo firfircoon wuxuu geli karaa fariimihiisa, xitaa haddii aan loo qoondeyn
  maamulka notifications-ka. Abuurista fariimaha iyo maamulka logs-ku waxay
  weli u baahan yihiin oggolaanshahooda gaarka ah.
- All Users wuxuu abuurayaa nuqul gaar ah oo loogu talagalay account kasta oo
  firfircoon wakhtiga dirista. Read-ka qof keliya ma beddelayo kan dadka kale.
- Qof aan ahayn qaataha ma beddeli karo Read-ka fariinta. Isticmaalayaasha caadiga
  ah ma soo bandhigi karaan inbox-ka dadka kale iyagoo beddelaya URL-ka.
- Gambaleelka iyo kaarka Unread waxay tirinayaan fariimaha qofka galay account-ka.
  Gambaleelku wuxuu hubiyaa fariimaha cusub 20 ilbiriqsi kasta inta boggu muuqdo.
  Notification Center wuxuu soo bandhigayaa Show new notifications marka fariin
  cusub timaaddo iyadoo boggu furan yahay.
- Siddeedda nooc ee foomamka waxay ogeysiinayaan accounts-ka firfircoon ee leh
  oggolaanshaha Approve ee foomkaas marka loo gudbiyo ansixinta. Qofkii sameeyey
  laguma daro liiska ansixiyayaasha foomkiisa. Go'aanka dib-u-eegista waxaa loo
  diraa qofkii foomka sameeyey.
- Fariimaha documents, milestones iyo payment requests waxay hadda ku xidhmaan
  isla Notification Center-ka. Ogeysiisyada lacag-bixinta ee hore u lumi jiray
  ka dib commit-ka waa la kaydiyaa.
- Email-ka waxaa la isku dayaa ka dib marka fariinta gudaha iyo diiwaanka
  email-ka database-ka lagu kaydiyo. SMTP oo fashilma ma luminayo fariinta ERP-ga.
  Log-gu wuxuu sheegaa Sent ama Failed iyo sababta. Email aan la dooran gacanta
  laguma geliyo saf diris aan loo baahnayn. All Users iyo Send Email Now waxay
  isku dayaan email gaar ah account kasta.
- Target User aan jirin ama aan firfircoonayn wuxuu soo saaraa qalad; fariinta
  looma beddelo ogeysiis guud. Phone maqan wuxuu keenaa SMS log Failed oo cad.
- Mark Sent ee SMS Queue wuxuu cusboonaysiiyaa log-ga ku xidhan. Tallaabadani
  wali waa calaamad gacanta ah; ma aha diris SMS API ah.

## Sida loo rakibo

ZIP-kani wuxuu ka kooban yahay ERP-ga oo dhan. Hagaajinta notifications-ku
waxay ku dul dhisan tahay ZIP-kii aad dirtay.

1. Xidh ERP-ga socda. Kaydi nuqul database-ka, `.env` iyo uploads-ka hadda jira.
2. Fur ZIP-ka. Ku beddel koodhka application-ka faylasha ku jira `erp_work`,
   adigoo ilaalinaya database-kaaga, `.env`, uploads-ka iyo Python environment-ka.
3. Gudaha folder-ka application-ka, iyadoo Python environment-kiisu shaqaynayo,
   socodsii:

   ```powershell
   python -m flask --app wsgi db upgrade
   ```

4. Dib u bilow ERP-ga sida aad hore ugu bilaabi jirtay. SQLite-ga lagu bilaabo
   `python run.py` wuxuu sidoo kale socodsiiyaa migrations-ka si otomaatig ah.
   PostgreSQL ama `serve_waitress.py` isticmaalayaasha waa inay amarka kore
   socodsiiyaan ka hor inta aan server-ka la bilaabin.
5. Browser-ka cusboonaysii, kadibna gal account-ka qaataha.

Migration-ka cusub waa `b20k0000a003`. Wuxuu ogeysiisyadii hore ee guud iyo
fariimihii workflow-ga u sameeyaa inbox copies gaar ah. Diiwaannadii asalka ahaa
waa la hayaa. Ogeysiis guud oo hore Read u ahaa lama garan karo qofkii dhab
ahaan akhriyey, sidaas darteed copies-ka loo sameeyo dadka firfircoon waxay
ka bilaabmaan Unread. Migration-ku email hore dib uma diro.

## Sida loo isticmaalo

**Fariin gacanta ah:** System → Create Notification → buuxi Title iyo Message →
dooro Target User → Save Notification. Qofka helaya wuxuu ka arkaa gambaleelka
ama System → Notifications. Read wuxuu calaamadiyaa akhriskiisa oo keliya.

**Foom ansixin loo gudbinayo:** Project Forms → fur foomka → Submit for Approval.
Hubi Status = Submitted. Account kale oo leh Approve permission wuxuu heli doonaa
ogeysiiska; marka uu Review sameeyo, qofkii foomka sameeyey wuxuu helayaa go'aanka.
Admin-ku waa inuu hubiyaa in uu jiro ugu yaraan hal account firfircoon oo kale
oo ansixin kara foomka. Foom sameeyuhu ma ansixin karo foomkiisa.

**Email:** dejinta SMTP waa inay sax tahay. Create Notification ka calaamadi
Send Email Now haddii loo baahan yahay. Notification Log ka hubi natiijada.
Sent waxay ka dhigan tahay in SMTP aqbalay dirista, ma aha xaqiijin in qaatahu
fariinta akhriyey. Email-ka dhabta ah ee server-kaaga laguma tijaabin hawshan.

**Email Failed:** sax SMTP ama cinwaanka kadib isticmaal Send Email ee log-ga.
Email hore Sent u ah mar labaad lagama dirayo badhankaas.

Haddii server-ku xirmo ka hor isku dayga email-ka, safkii Queued wuu sii jiraa.
Maamuluhu wuxuu soo kicin karaa safka iyadoo application folder-ka la joogo:

```powershell
python -m flask --app wsgi notifications-send
```

Si si ula kac ah dib loogu tijaabiyo kuwii Failed noqday:

```powershell
python -m flask --app wsgi notifications-send --retry-failed
```

Amarka dib-u-diristu wuxuu dirayaa email dhab ah marka SMTP shaqaynayo. Haddii
log-ku ku xayirmo Sending ka dib server interruption, marka hore hubi diiwaanka
SMTP; si otomaatig ah looma celiyo diris natiijadeeda aan la hubin. Tani waxay
yaraynaysaa fariimo laba jeer la diro. Safkani ma laha adeeg retry joogto ah.
Kooxo aad u badan oo email hal mar loo diro waxay kordhin karaan wakhtiga
codsiga, maadaama isku dayga koowaad lagu sameeyo isla codsiga server-ka.

## Xaqiijinta

- 84 tijaabo ayaa guulaystay, oo ay ku jiraan 20 tijaabo oo cusub oo notifications-ka ah.
- PostgreSQL integration waa laga booday maadaama test DSN aan la hayn.
  Tijaabada native PDF waa laga reebay wareeggan; PDF code lama beddelin.
- Waxaa la tijaabiyey kala-soocidda dadka, Broadcast/Read, dhammaan siddeedda
  nooc ee foomamka, email fashil iyo dib-u-dirid, rollback, migrations iyo CLI.
- Browser-ka waxaa lagu xaqiijiyey: account caadi ah oo aan maamulka notifications
  haysan ayaa fariintiisa helay; gambaleelku wuxuu isu beddelay 0 → 1 iyada oo
  aan bogga dib loo furin; fariinta qofka kale ma muuqan; Read wuxuu tirada
  ugu celiyey 0. Wax JavaScript error ah laguma arag socodkan.
- Database-yo tijaabo ah ayaa la isticmaalay. Email, SMS iyo WhatsApp dhab ah
  cidna looma dirin. Server-kaaga shaqaynaya hawshani ma beddelin; rakibidda
  ZIP-kan iyo migration-ka ayaa looga baahan yahay installation-kaaga.
