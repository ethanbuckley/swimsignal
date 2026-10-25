# Met Office marine data (UKMCAS): order form answers and email, for Ethan to send

Drafted 24 October 2026. Nothing has been sent. Claude cannot send it or register for you.

Read `docs/SEA-CURRENTS-SCOPING-2026-10.md` first. Its advice is short:
- **Do not send this yet unless coastal spots become a priority.** UKMCAS has no archive. It only gives the next
  7 days and the last 2. So it cannot back-test anything. It is for a live forecast after a test passes.
- **For a back-test at 1.5 km, a free Copernicus Marine account is the quicker route.** It holds the same AMM15
  hourly surface currents from 29 September 2023. See step 0 below.

## Step 0, if you want the back-test data first: a Copernicus Marine account

1. Go to `https://data.marine.copernicus.eu/register` and register with your own name and email.
2. Accept the Copernicus Marine Service licence when asked. Read it first: it asks for a credit line.
3. You will know it worked when you can open
   `https://data.marine.copernicus.eu/product/NWSHELF_ANALYSISFORECAST_PHY_004_013/services` and see the
   dataset `cmems_mod_nws_phy-cur_anfc_1.5km-2D_PT1H-i` with a download option.
4. Then store the username and password in the Keychain, as the push key is, not in the repo.

The mistake most likely here: using a work address. Use the project address, so the account stays with the project
if your job changes.

## The UKMCAS order form

The form is a two-page PDF: `https://www.metoffice.gov.uk/api/assets/file/data-product-order-formpdf?prefix=assets`.
Before you fill it, read the product terms and the Service Information Sheet that the order page links to
(`https://www.metoffice.gov.uk/services/data/met-office-marine-data-service`, steps 1 and 2 there).

Below are the form's fields in its own order, with the answer to type. Square brackets are yours to fill.

### Your Details

| Field | Answer |
|---|---|
| Organisation name | SwimSignal (an independent, non-profit project run by Ethan Buckley) |
| Contract Contact Name | Ethan Buckley |
| Position | Founder and developer |
| Telephone NWH | [your phone number] |
| E-mail | hello@swimsignal.co.uk |
| Operational/Delivery Contact | Ethan Buckley |
| Position | Founder and developer |
| Telephone NWH | [your phone number] |
| Telephone ONWH | [the same number, or leave blank] |
| E-mail | hello@swimsignal.co.uk |

NWH means normal working hours. ONWH means outside them. The Service Information Sheet defines normal working hours
as 08:30 to 17:00 Monday to Thursday and 08:30 to 16:30 Friday.

Check before you use hello@swimsignal.co.uk that mail to it reaches you. If not, give the address you read daily.

### Your Data Product Request

| Data Product | Requesting access? | Intended Use |
|---|---|---|
| AMM15 | Yes | Hourly surface currents and sea surface height near English coastal bathing waters, to test whether currents that carry sewage overflow discharges towards a beach explain its E. coli samples, and if they do, to add that to SwimSignal's free public sewage-risk forecast for swimmers (swimsignal.co.uk). Credited "© Crown copyright, Met Office". |
| AMM15 Wave | (leave blank) | (leave blank) |
| AMM7 | (leave blank) | (leave blank) |
| OSTIA | (leave blank) | (leave blank) |
| Global Ocean | (leave blank) | (leave blank) |

**Data Product Collection Method:** tick **SFTP**. It is the encrypted one of the two.

### Your Customer Commitments

- Tick the first box: "I confirm that I have read and understood the OGL ... and agree to provide the following
  acknowledgement when using the data '© Crown copyright, Met Office'". Read the OGL first:
  `https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/`.
- Leave the second box (OSTIA, CC BY) unticked. It is not requested.

## The email

To: enquiries@metoffice.gov.uk
Subject: UKMCAS data product order: AMM15 (SwimSignal)
Attach: the filled order form, saved as PDF.

> Hello,
>
> Please find attached a Data Product Order Form for access to the AMM15 product through the UK Marine and Climate
> Advisory Service, collected by SFTP.
>
> SwimSignal is a free public forecast of sewage-overflow risk at swimming spots in England. We would like to test
> whether surface currents near coastal bathing waters help explain the Environment Agency's E. coli samples there,
> and if they do, use them in the forecast. We would credit the data "© Crown copyright, Met Office".
>
> Two questions, if you can answer them:
> 1. Is any back-catalogue of the AMM15 hourly surface currents (SSC) available through UKMCAS, for example the
>    2024 to 2026 bathing seasons? Your FAQ says the folder keeps three days.
> 2. We only need the surface current files (SSC, hourly) and sea surface height (SSH, hourly). Is it possible to
>    collect only those files, to keep our downloads small?
>
> Thank you,
> Ethan Buckley
> SwimSignal, hello@swimsignal.co.uk

## What happens next, and how you will know it worked

1. Set-up can take up to 15 working days (the order page says so).
2. You will get an email with FTP credentials and collection guidance.
3. Files arrive once a day. The AMM15 product sheet gives about 08:30 UTC; the order page gives about 09:30 UTC.
   Only three days are kept. So a collector must run every day, or days are lost for good.
4. It worked when you can list the folder by SFTP and see a file named like
   `metoffice_foam1_amm15_NWS_SSC_b<date>_hi<date>.nc`.

Nothing in the repo collects these files yet. Do not set it up until a test has passed: an unused daily download
is a job someone has to keep running.
