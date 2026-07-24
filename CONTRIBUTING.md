# Contributing

The fastest way to help: **add companies.** More companies = more internships.

## Add a company (one line)

1. Find the company's ATS token from their careers "Apply" URL:
   - `boards.greenhouse.io/`**`stripe`** → slug is `stripe`
   - `jobs.lever.co/`**`plaid`** → slug is `plaid`
   - `jobs.ashbyhq.com/`**`openai`** → slug is `openai`
2. Add an entry to [`data/candidates.json`](data/candidates.json):
   ```json
   {"name": "Stripe", "slug": "stripe"}
   ```
3. Re-validate and refresh locally:
   ```bash
   python run.py harvest   # detects which ATS the slug lives on
   python run.py update    # refreshes listings, README, and CSV
   ```
4. Open a pull request.

The harvester auto-detects the ATS (Greenhouse, Lever, Ashby, SmartRecruiters,
Rippling, Workable, Breezy, Recruitee), so you only need the name + slug.
Workday/Oracle tenants need a `wd`/`site` (or `host`/`site`) pair — easiest is
to run `python run.py discover` (it mines them from public datasets), or copy
the shape of an existing entry in `data/companies.json`.

## Run locally

```bash
python -m venv .venv
# Windows:        .\.venv\Scripts\activate
# macOS / Linux:  source .venv/bin/activate
pip install -r requirements.txt
python run.py all      # harvest + update
```

## Tuning what counts as an internship

All the classification (internship / tech / season / category) lives in one
file: [`src/intern_engine/filters.py`](src/intern_engine/filters.py). PRs that
improve precision/recall against real titles are very welcome.

## Improving the sponsorship flags

The 🇺🇸 / 🛂 flags come from
[`src/intern_engine/sponsorship.py`](src/intern_engine/sponsorship.py), which
matches phrases employers actually write. Found a posting it gets wrong? Add
the phrase to the right pattern **with a test** in
`tests/test_sponsorship.py` — precision matters more than recall here.


## Wanted Companies (Missing Connectors)

The following companies are known to hire actively (specifically in the Indian market), but we currently lack an automated ATS connector for them. If you can find their ATS careers page URL, please add them to data/candidates.json!

<details>
<summary>Click to expand the list of wanted company slugs</summary>

- 1kosmos
- accelya
- accolite
- adp
- aetion
- affinity
- airbus
- airtel
- akamai
- akuna-capital
- alibaba
- allincall
- alphonso
- alten
- altimetrik
- amadeus
- amd
- amdocs
- american-airlines
- american-express
- analytics-quotient
- andela
- anduril
- aon
- appdynamics
- appfolio
- apple
- applied-intuition
- aqr-capital-management
- arcesium
- argo-ai
- arista-networks
- ascend
- audible
- auriga
- aurora
- avalara
- avito
- axis-bank
- baidu
- bank-of-america
- bcg
- bending-spoons
- bill-com
- blackbuck
- blend
- blinkit
- blue-origin
- bnp-paribas
- bny-mellon
- bolt
- bookingcom
- box
- bp
- bridgewater-associates
- brillio
- bt-group
- buyhatke
- bytedance
- c3-ai
- capgemini
- capital-one
- careem
- cars24
- carwale
- cashfree
- caterpillar
- cerner
- chalo
- checkpoint
- chewy
- chubb
- citadel
- citrix
- clari
- cleartrip
- clutter
- cme-group
- cockroach-labs
- code-studio
- coditas
- cognizant
- coindcx
- coinswitch-kuber
- couchbase
- coveo
- cruise-automation
- ctc
- curefit
- cvent
- cyntexa
- cyware
- dailyhunt
- dassault-sysetmes
- dataart
- de-shaw
- delhivery
- deloitte
- deltax
- deutsche-bank
- directi
- discovery
- dji
- docusign
- doordash
- dp-world
- drawbridge
- drw
- dtcc
- dunzo
- edelweiss
- electronic-arts
- elitmus
- envoy
- epam-systems
- epic-games
- epic-systems
- ericsson
- exl
- ey
- f5-networks
- fallible
- fanatics
- fast
- fastenal
- fidelity
- fidessa
- fiverr
- flatiron-health
- fleetx
- flexera
- fortinet
- forusall
- fpt
- fractal-analytics
- freecharge
- fynd
- gameskraft
- garena
- garmin
- ge-digital
- ge-healthcare
- general-electric
- general-motors
- gilt-groupe
- github
- glassdoor
- globallogic
- glovo
- gojek
- goldman-sachs
- grammarly
- graviton
- groupon
- grubhub
- gsa-capital
- gsn-games
- harness
- hashedin
- hbo
- hcl
- helix
- hilabs
- honey
- honeywell
- hopper
- hotstar
- houzz
- hrt
- hsbc
- htc
- huawei
- hubspot
- hulu
- ibm
- iit-bombay
- impact-analytics
- impetus
- increff
- indeed
- info-edge
- informatica
- interactive-brokers
- intuit
- ivp
- ixl
- jane-street
- jeavio
- jingchi
- jio
- josh-technology
- jtg
- jump-trading
- juspay
- kakao
- kickdrum
- kla-tencor
- kotak-mahindra-bank
- kpmg
- larsen-toubro
- leap-motion
- lendingkart
- lg-electronics
- liberty-mutual
- liftoff
- lime
- line
- lowe
- lti
- lucid
- luxoft
- machine-zone
- machinezone
- makemytrip
- mapbox
- maq-software
- mathworks
- mcdonalds
- mckinsey
- medianet
- meituan
- mercari
- meta
- micro1
- microstrategy
- millennium
- mindtree
- mishipay
- mitsogo
- mobileye
- mobisy
- moengage
- moneylion
- morgan-stanley
- motive
- moveworks
- mphasis
- msci
- murex
- mykaarma
- myntra
- nagarro
- national-instruments
- national-payments-coorperation-india
- natwest
- navan
- naver
- navi
- nerdwallet
- netapp
- netcracker-technology
- netease
- netsuite
- nextjump
- niantic
- nielsen
- nokia
- noon
- npci
- nutanix
- nykaa
- odoo
- okx
- olx
- opentext
- oppo
- optiver
- optum
- oracle
- oscar-health
- otterai
- ozon
- palo-alto-networks
- park
- paycom
- paypay
- payu
- peak6
- pega
- persistent-systems
- pickrr
- playsimple
- pocket-gems
- polar
- ponyai
- pornhub
- porter
- postmates
- poynt
- practo
- publicis-sapient
- pure
- pure-storage
- purplle
- qualcomm
- qualtrics
- qualys
- quantiphi
- rackspace
- radius
- rally-health
- ramp-2
- redbus
- reliance-retails
- retailmenot
- revolut
- riot-games
- ripple
- rivian
- sambanova
- samsung
- sap
- scale-ai
- scaler
- schlumberger
- schneider-electric
- schrodinger
- shift-technology
- shipsy
- shopback
- shopee
- shopify
- shopup
- siemens
- sig
- smartnews
- snapdeal
- societe-generale
- softwire
- sony
- soundhound
- splunk
- square
- squarepoint-capital
- squarespace
- src
- starbucks
- state-farm
- syfe
- symantec
- synopsys
- ta-digital
- tableau
- tanium
- tcs
- tech-mahindra
- teradata
- tesco
- tesla
- texas-instruments
- the-trade-desk
- thomson-reuters
- thousandeyes
- tiger-analytics
- tiktok
- tinder
- tinkoff
- tokopedia
- tomtom
- toptal
- tower-research
- tracxn
- traveloka
- trend-micro
- trilogy
- triplebyte
- tusimple
- twitter
- two-sigma
- ubisoft
- ubs
- udemy
- ukg
- unbxd
- unity
- unstop
- upstart
- urban-company
- ust
- valve
- verily
- veritas
- viasat
- vimeo
- virtusa
- vk
- vmware
- walmart-labs
- warnermedia
- wayfair
- wells-fargo
- western-digital
- winzo
- wish
- wissen
- wix
- works-applications
- xing
- yahoo
- yandex
- yatra
- yelp
- zalando
- zappos
- zemoso
- zenefits
- zeta-suite
- ziprecruiter
- zluri
- zoho
- zopsmart
- zs-associates
- zulily
- zynga

</details>
