# Signing and notarization

## The two platforms do different things

| | macOS | Windows |
|---|---|---|
| **Signing** | Developer ID Application certificate, `codesign` with hardened runtime | Authenticode, via **Azure Trusted Signing** |
| **Notarization** | Yes — Apple scans the bundle, you staple a ticket | **No such service** |
| **What the user sees** | Gatekeeper passes; no "damaged app" dialog | SmartScreen publisher name builds reputation over time |

**"Notarize Windows" is not a thing.** Windows has no notarization step; the
equivalent outcome is Authenticode signing, which establishes the publisher
identity. Anyone asking for "Windows notarization" means signing.

---

## macOS

### Secrets (six)

| Secret | Value |
|---|---|
| `MACOS_CERT_P12_BASE64` | `base64 -i cert.p12` — the exported Developer ID Application cert + key |
| `MACOS_CERT_PASSWORD` | the `.p12` export password |
| `MACOS_SIGN_IDENTITY` | `Developer ID Application: Security Ronin Ltd (TEAMID)` |
| `MACOS_NOTARY_KEY_P8_BASE64` | `base64 -i AuthKey_XXXX.p8` |
| `MACOS_NOTARY_KEY_ID` | the App Store Connect API Key ID |
| `MACOS_NOTARY_ISSUER_ID` | the API Issuer ID (a UUID) |

Setup, in order:

1. **Apple Developer Program**, enrolled as the *organization* "Security Ronin Ltd"
   (needs a D-U-N-S number; 1–5 business days). Note the **Team ID**.
2. **Developer ID Application** certificate (developer.apple.com → Certificates → +).
   Export cert + private key as `.p12`.
3. **Notarization key** — appstoreconnect.apple.com → Users and Access →
   Integrations → App Store Connect API → + → role Developer → download the
   `.p8` **once** (Apple will not show it again).

### What CI does

1. Import the `.p12` into a throwaway keychain.
2. Sign **inside-out**. The frozen Python engine is a second Mach-O inside
   `Contents/MacOS/`. Notarization rejects a bundle whose nested code lacks a
   hardened-runtime signature, and `--deep` is not a reliable substitute, so the
   workflow walks `Contents/MacOS`, signs every Mach-O, then signs the bundle.
3. `xcrun notarytool submit --wait`, then `xcrun stapler staple`.
4. Rebuild the `.dmg` **after** stapling, so the shipped image carries the ticket.

### Verify locally

```sh
codesign --verify --deep --strict --verbose=2 "PDF to DOCX.app"
spctl --assess --type execute --verbose=2 "PDF to DOCX.app"
xcrun stapler validate "PDF to DOCX.app"
```

---

## Windows

### Secrets (three) and prerequisites (three)

| Secret | Value |
|---|---|
| `AZURE_CLIENT_ID` | app registration (service principal) client ID |
| `AZURE_TENANT_ID` | Entra tenant ID |
| `AZURE_SUBSCRIPTION_ID` | subscription containing the signing account |

Prerequisites that are **not** secrets and must exist first:

1. An **Azure Trusted Signing account** (`securityronin`) and a **certificate
   profile** (`securityronin-public`) in a supported region — the workflow uses
   `https://neu.codesigning.azure.net`.
2. A **federated credential** on the app registration whose subject is
   `repo:<owner>/<repo>:environment:release`. A classic federated credential
   **cannot wildcard tag refs**, which is why the job pins
   `environment: release`.
3. The identity needs the **Trusted Signing Certificate Profile Signer** role.

### Why `azure/login` comes first

`trusted-signing-action` authenticates with `DefaultAzureCredential`, which does
**not** perform the GitHub OIDC exchange itself. Without the preceding
`azure/login` step the signer fails with
`AzureCliCredential: Please run 'az login'`. The login trades the id-token for
a session the signer then rides — no client secret is stored.

### What gets signed

Three separate passes, because a signature on the installer does not cover the
binaries inside it and vice versa:

- `*.exe` under `target/release` — the app and the frozen engine sidecar
- `*.msi` under `bundle/`
- `*-setup.exe` (NSIS) under `bundle/`

All with SHA-256 file digest and RFC 3161 timestamping
(`http://timestamp.acs.microsoft.com`), so signatures outlive the certificate.

### Verify locally

```powershell
Get-AuthenticodeSignature .\PDF*.msi | Format-List
signtool verify /pa /all .\PDF*.msi
```

---

## What this does not do

- **No credentials are included.** Every signing step is gated on its secrets
  being present; until they are, the build produces an **unsigned** installer.
  An unsigned macOS `.app` is Gatekeeper-blocked, and an unsigned Windows
  installer shows "Unknown publisher".
- **Windows ARM64 is not built.** Add a `windows-11-arm` runner if needed.
- **No Apple hardened-runtime exception for JIT** would be needed by a
  JavaScript engine compiled into the app; WebView2/WKWebView run out of process,
  so the entitlements in `app/src-tauri/entitlements.plist` are limited to what
  the sidecar needs.
