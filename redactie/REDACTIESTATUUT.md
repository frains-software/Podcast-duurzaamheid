# Redactiestatuut Grondstof

> Dit document is de opdracht voor iedereen die een aflevering schrijft: de dagelijkse
> Claude-routine, de automatische terugvaloptie in GitHub Actions, of een mens.
> Het resultaat is één bestand: `redactie/JJJJ-MM-DD.json`. De studio maakt daar
> daarna automatisch audio van met de gekloonde stem van Frans (ElevenLabs Eleven v4).

## 1. Wat is Grondstof?

Een dagelijks **zakelijk nieuwsbulletin van vijf minuten** over duurzaamheid en circulaire
economie. Het klinkt als een radionieuwsbulletin op een zakenzender: rustig, helder,
feitelijk en met gezag. Er wordt niet gekletst of gegrapt en er worden geen meningen
verkondigd. De luisteraar is een professional (inkoper, facilitair manager,
duurzaamheidsmanager, ondernemer of beleidsmaker) die in vijf minuten bij wil zijn.

**Afzender.** Frans van den Berge presenteert, **niet als privépersoon maar namens De Graaf
Groep** en de bedrijven waarvoor hij werkt: De Graaf Groep (afvalinzameling en recycling
sinds 1952, motto *"Today's Waste, Tomorrow's Products"*), Wastenet (de onafhankelijke
afvalmanager), Circular&Co. (circulaire herbruikbare bekers en drinkwaren) en
Product for Product (circulair inkopen: Paper for Paper, Green2office, Waste2promo).
Gebruik dus "wij" en "bij De Graaf Groep", geen persoonlijke anekdotes.

## 2. Nieuwsselectie

- **Actualiteit:** nieuws van de afgelopen 24 uur, desnoods 72 uur (maandag en het weekend).
  Nooit iets dat al in een van de vorige zeven afleveringen stond (bekijk `redactie/`),
  behalve als er een echte nieuwe ontwikkeling is.
- **Vier verhalen** met deze mix (wijk af als het nieuws daarom vraagt):
  1. **Beleid & regelgeving:** Nederland en de EU. Denk aan de verpakkingsverordening (PPWR),
     CSRD en omnibus, de Ecodesign-verordening (ESPR), het digitaal productpaspoort, de
     uitgebreide producentenverantwoordelijkheid (UPV), de wegwerpplasticrichtlijn (SUP),
     de afvalstoffenheffing, CO₂-heffing en het Nationaal Programma Circulaire Economie.
  2. **Markt & bedrijven:** grondstofprijzen (oud papier, metaal, kunststof), investeringen,
     faillissementen, overnames, ketens en inkoop.
  3. **Innovatie & techniek:** recycling, materialen, hergebruiksystemen, biobased,
     chemische recycling, retourlogistiek.
  4. **Afval & grondstoffen in de praktijk:** de sector zelf, gemeenten, inzameling,
     statiegeld, onderzoek, cijfers van het CBS, Rijkswaterstaat of Eurostat.
- **Betrouwbare bronnen**, bij voorkeur primair: Rijksoverheid, Europese Commissie, CBS,
  RIVM, PBL, Rijkswaterstaat, NOS, FD, NRC, Trouw, Change Inc., Duurzaam Ondernemen,
  Afvalgids, Recycling Magazine, Euractiv, Reuters, Bloomberg, Financial Times, ESG Today,
  Circle Economy, Ellen MacArthur Foundation, Packaging Europe, Euwid.
  Minimaal één bron per verhaal, met werkende URL.
- **Feitencheck:** elk getal, elke naam en elke datum moet in de bron staan. Twijfel? Laat het weg.
  Verzin nooit nieuws. Is het een rustige nieuwsdag, kies dan een relevant rapport of
  een achtergrondverhaal dat deze week verscheen, en zeg dat eerlijk.

## 3. Opbouw van een aflevering (ongeveer 620 tot 700 woorden)

| # | `kind`    | Inhoud | Woorden |
|---|-----------|--------|---------|
| 1 | `intro`   | Begroeting met dag en datum, naam van het programma, presentator en rol, daarna de drie belangrijkste koppen. | 50–70 |
| 2 | `story` ×4 | Een nieuwsbericht: eerst de kern (wie, wat, waar, wanneer), dan de context en tot slot het "waarom het ertoe doet". | 100–130 per stuk |
| 3 | `insight` | **De duiding:** wat betekent het nieuws van vandaag voor organisaties? Vanuit de praktijk van De Graaf Groep en de zusterbedrijven. Concreet, nuchter en **geen verkooppraatje**. Noem hooguit één bedrijf, en alleen als het echt past. | 80–100 |
| 4 | `number`  | **Het cijfer van de dag:** één opvallend getal uit het nieuws, met uitleg. | 30–45 |
| 5 | `outro`   | Afsluiting: "Dat was Grondstof voor vandaag…", plus wanneer de volgende aflevering komt (morgen om negen uur). | 30–45 |

### Vaste formuleringen

- Intro, voorbeeld: *"Goedemorgen. Het is vrijdag negen oktober. U luistert naar Grondstof,
  het circulaire nieuwsbulletin van De Graaf Groep. Ik ben Frans van den Berge. Dit zijn de
  koppen. …"*
- Overgang naar de duiding, voorbeeld: *"En wat betekent dit voor uw organisatie?"*
- Outro, voorbeeld: *"Dat was Grondstof voor vandaag. De bronnen bij elk bericht vindt u in
  de app en in de shownotes. Morgen om negen uur bent u weer bij. Tot dan."*

## 4. Schrijven voor het oor (belangrijk voor de stem)

- Schrijf **korte zinnen** (gemiddeld 12 tot 16 woorden), in de actieve vorm en de **u-vorm**.
- **Schrijf getallen, bedragen, percentages en datums voluit in woorden**: "twee komma vier
  miljard euro", "achtentwintig procent", "negen oktober", "tweeduizend dertig".
- **Geen afkortingen die de stem kan verhaspelen.** Schrijf ze uit of fonetisch: "CO-twee",
  "de Europese verpakkingsverordening" (niet "PPWR"), "de E-U" mag als "de Europese Unie".
  Bedrijfsnamen schrijf je zoals je ze uitspreekt: "Circular and Co".
- **Geen** haakjes, slashes, opsommingstekens, URL's, emoji of markdown in `text`.
- Bronvermelding gebeurt hardop en kort: "meldt het Financieele Dagblad", "volgens het CBS".
- Geen hype en geen superlatieven ("baanbrekend", "gamechanger"), geen meningen en geen
  vraag-en-antwoordtrucs. Nuance is wel welkom: duurzaamheid is zelden zwart-wit.
- Audio-tags tussen blokhaken (zoals `[pause]`) **niet gebruiken**: de studio regelt pauzes,
  tunes en overgangen zelf.

## 5. Bestandsformaat

Bestandsnaam: `redactie/JJJJ-MM-DD.json` (datum van uitzending, tijdzone Europe/Amsterdam).

```json
{
  "date": "2026-10-09",
  "title": "Korte, krachtige titel van de aflevering (max. 70 tekens)",
  "summary": "Eén of twee zinnen voor de shownotes en de app (max. 300 tekens).",
  "segments": [
    { "kind": "intro", "text": "Goedemorgen. Het is …" },
    {
      "kind": "story",
      "headline": "Kop zoals hij in de app verschijnt (max. 80 tekens)",
      "text": "Gesproken tekst …",
      "sources": [
        { "publisher": "NOS", "title": "Titel van het artikel", "url": "https://…" }
      ]
    },
    { "kind": "story", "headline": "…", "text": "…", "sources": [ … ] },
    { "kind": "story", "headline": "…", "text": "…", "sources": [ … ] },
    { "kind": "story", "headline": "…", "text": "…", "sources": [ … ] },
    { "kind": "insight", "headline": "Wat betekent dit voor u?", "text": "…" },
    { "kind": "number", "headline": "Het cijfer van de dag", "text": "…" },
    { "kind": "outro", "text": "Dat was Grondstof voor vandaag. …" }
  ],
  "number_of_the_day": {
    "value": "85%",
    "label": "Korte uitleg voor op het scherm (max. 90 tekens)",
    "source": { "publisher": "CBS", "title": "…", "url": "https://…" }
  }
}
```

`number_of_the_day.value` is voor het scherm en mag dus wél cijfers en tekens bevatten.

## 6. Controle

Draai na het schrijven altijd:

```bash
python3 -m studio validate JJJJ-MM-DD
```

De validator controleert de structuur, de lengte (doel: 4:45 tot 5:20 minuten inclusief tunes), cijfers in
gesproken tekst, afkortingen en bronnen. Los alle **fouten** op en bij voorkeur ook alle
**waarschuwingen**.
