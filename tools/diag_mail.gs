/**
 * Reçoit les diagnostics envoyés par IcueLite et les transmet par courriel au propriétaire du script.
 *
 * Mise en place (une fois) : script.google.com > Nouveau projet, coller ce fichier, Déployer >
 * Nouveau déploiement > type « Application Web », Exécuter en tant que « Moi », Accès « Tout le monde »,
 * autoriser l'accès à Gmail, puis copier l'URL (…/exec) dans icuelite/diag.py (SCRIPT_URL).
 */
function doPost(e) {
  var data = JSON.parse(e.postData.contents || "{}");
  if (data.source !== "icuelite" || !data.diagnostic) {
    return reply({ success: false, message: "requête inconnue" });
  }
  var text = String(data.diagnostic).slice(0, 2000000);
  MailApp.sendEmail({
    to: Session.getEffectiveUser().getEmail(),
    subject: String(data._subject || "IcueLite - diagnostic").slice(0, 200),
    body: "Diagnostic IcueLite " + (data.version || "") + " envoyé depuis " + (data.appareil || "?") +
          ".\nLe rapport complet est en pièce jointe.\n\n" + text.slice(0, 20000),
    attachments: [Utilities.newBlob(text, "text/plain", "icuelite-diag.txt")]
  });
  return reply({ success: true });
}

function reply(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
