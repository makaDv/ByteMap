# Guida all'uso di ByteMap (italiano)

ByteMap mostra cosa occupa spazio sul disco: cartelle e file più grandi, file vecchi e
duplicati. Funziona **completamente offline**: nessun dato lascia il tuo computer.

## 1. Requisiti

- Windows, macOS o Linux.
- Python 3.10 o più recente ([python.org](https://www.python.org/downloads/)).
  Su Windows, durante l'installazione spunta "Add python.exe to PATH".

## 2. Scaricare ByteMap

Con git:

```bat
git clone https://github.com/makaDv/ByteMap.git
cd ByteMap
```

Senza git: sulla pagina GitHub premi **Code → Download ZIP**, estrai lo ZIP e apri la cartella.

## 3. Avviare l'interfaccia grafica

Scegli uno dei modi:

- **Doppio clic** su `ByteMap.pyw` nella cartella del progetto.
- Dal Prompt dei comandi, dentro la cartella del progetto:

  ```bat
  python -m bytemap
  ```

Non serve installare nulla: l'interfaccia usa Tkinter, già incluso in Python.

> **PC aziendali con Device Guard / criteri di sicurezza:** se `pip` o altri programmi sono
> bloccati, usa `python -m bytemap` dalla cartella del progetto. Non cercare di aggirare i
> criteri dell'organizzazione: in caso di dubbio chiedi al supporto IT.

## 4. Usare l'interfaccia

1. **Folder**: scrivi una cartella o premi **Browse...**, poi **Scan**.
2. Le schede mostrano i risultati:
   - **Folders**: sottocartelle ordinate per dimensione. Doppio clic per entrare, **Up** per tornare su.
   - **Big files**: i file più grandi.
   - **Old files**: file non modificati da N giorni (imposta i giorni in alto).
   - **Duplicates**: premi **Find duplicates**. I file vengono confrontati per contenuto (SHA-256).
3. **Min file size** e **days**: cambia i valori e premi **Apply filters**.
4. Clic su un'intestazione di colonna per ordinare. Ctrl+clic o Maiusc+clic per selezionare più righe.
5. Azioni sulle righe selezionate:
   - **Show in folder**: apre Esplora file sul file.
   - **Copy path**: copia il percorso.
   - **Move to Recycle Bin** (o tasto Canc): sposta nel **Cestino**, dopo una conferma.
     Puoi ripristinare i file dal Cestino. ByteMap non cancella mai in modo definitivo.
6. **Export HTML report...**: salva un report con mappa interattiva. Lascia spuntato
   **Hide my home folder in report** per nascondere `C:\Users\<nome>`.

### Protezioni integrate

- Rifiuta radici del disco e cartelle di sistema (`C:\Windows`, `C:\Program Files`, `/usr`, ...).
- Non segue né sposta collegamenti simbolici e junction.
- Nei duplicati impedisce di spostare **tutte** le copie di un file.

## 5. Riga di comando (opzionale)

```bat
python -m bytemap scan D:\                          :: cartelle più grandi
python -m bytemap big C:\Users\nome\Downloads       :: file più grandi
python -m bytemap old . --days 730 --min-size 50M   :: file vecchi
python -m bytemap dupes C:\Users\nome\Pictures      :: duplicati
python -m bytemap report C:\Users\nome --redact-home
python -m bytemap trash file.mp4                    :: prova, non sposta nulla
python -m bytemap trash file.mp4 --apply            :: sposta nel Cestino dopo "YES"
```

Opzioni comuni: `--top N`, `--min-size 10M`, `--exclude CARTELLA` (ripetibile).

## 6. Privacy

- ByteMap non raccoglie, non invia e non salva dati altrove. Vedi [PRIVACY.md](../PRIVACY.md).
- Il report HTML contiene i percorsi dei tuoi file: **non condividerlo** se sono privati.
- Se analizzi cartelle con dati personali di altre persone (per esempio in azienda),
  sei responsabile di farlo nel rispetto delle norme applicabili (GDPR incluso).
- Non pubblicare percorsi, screenshot o report personali nelle issue di GitHub.

## 7. Problemi frequenti

| Problema | Soluzione |
|---|---|
| `"bytemap" non è riconosciuto` | Usa `python -m bytemap` dalla cartella del progetto. |
| `No module named bytemap` | Non sei nella cartella del progetto: `cd` nella cartella `ByteMap`. |
| `pip.exe bloccato da Device Guard` | Non serve pip per la GUI. Usa `python -m bytemap`. |
| `No module named send2trash` | Serve solo per il Cestino: `python -m pip install Send2Trash` (se consentito). |
| Cartelle "unreadable" | Mancano i permessi: ByteMap le salta, è normale. |

## 8. Responsabilità

ByteMap è fornito "così com'è", senza garanzie (licenza [MIT](../LICENSE)).
Controlla sempre cosa sposti nel Cestino e mantieni backup dei dati importanti.
