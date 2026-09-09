/* Escaneo de codigo de barras.
 *
 * Un lector fisico USB/Bluetooth se comporta como teclado: escribe el codigo en
 * el input enfocado y manda Enter. Por eso basta con escuchar el submit del
 * campo; no hace falta libreria para ese caso.
 *
 * Para la camara del celular se agregara html5-qrcode en la etapa de captura de
 * notas (ver CONTEXTO_PROYECTO.md, seccion 6).
 */

async function buscarPorCodigo(codigo) {
  const url = `/catalogo/api/codigo?codigo=${encodeURIComponent(codigo)}`;
  const respuesta = await fetch(url, { headers: { Accept: "application/json" } });
  return respuesta.json();
}

// Conecta un <input data-escaner> con la API del catalogo.
// El evento "articulo-escaneado" lo consume el formulario de la nota de venta.
document.querySelectorAll("input[data-escaner]").forEach((input) => {
  input.addEventListener("keydown", async (evento) => {
    if (evento.key !== "Enter") return;
    evento.preventDefault();

    const codigo = input.value.trim();
    if (!codigo) return;

    const resultado = await buscarPorCodigo(codigo);
    input.value = "";
    input.dispatchEvent(
      new CustomEvent("articulo-escaneado", { detail: resultado, bubbles: true })
    );
  });
});
