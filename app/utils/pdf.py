"""Generacion del PDF de la remision con ReportLab.

El formato reproduce el del sistema anterior (_diseno_anterior/remisiones.html
y remision_documento.html): encabezado con la razon social que toca segun el
hospital, tabla de conceptos, totales con IVA, el recuadro punteado con los
campos que se llenan a mano en el hospital (paciente, habitacion, episodio,
aseguradora) y las tres firmas.
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

from app.constantes import Empresa, TipoRemision

GRIS = colors.HexColor("#6b7280")
NEGRO = colors.black
ROJO = colors.HexColor("#cc0000")

_normal = ParagraphStyle("avant", fontName="Helvetica", fontSize=8, leading=10)
_chico = ParagraphStyle("avant-chico", parent=_normal, fontSize=7, leading=8.5)
_negrita = ParagraphStyle("avant-negrita", parent=_normal, fontName="Helvetica-Bold")
_centrado = ParagraphStyle("avant-centrado", parent=_normal, alignment=1)
_centrado_chico = ParagraphStyle("avant-cc", parent=_chico, alignment=1)


def _moneda(valor):
    """Como en el sistema anterior: el cero se imprime vacio, no como $0.00."""
    numero = float(valor or 0)
    if numero == 0:
        return ""
    return f"$ {numero:,.2f}"


def _encabezado(remision):
    nota = remision.nota
    datos = Empresa.DATOS[Empresa.para_hospital(nota.hospital)]

    izquierda = Paragraph(
        '<font size="26" color="#9ca3af"><b>A V A N T</b></font>', _normal
    )
    centro = Paragraph(
        f"<b>{remision.razon_social or datos['razon_social']}</b><br/>"
        f"R.F.C. {remision.rfc or datos['rfc']}<br/>"
        f'<font size="6">{Empresa.DIRECCION}</font>',
        _centrado_chico,
    )
    # El folio ocupa toda la columna: a 12pt se partia en dos lineas.
    derecha = Paragraph(
        f'<b>REMISION N°</b><br/><font size="11" color="#cc0000"><b>'
        f"{remision.folio}</b></font><br/>"
        f'<font size="7">{remision.fecha_generacion.strftime("%d/%m/%Y")}</font>',
        ParagraphStyle("der", parent=_normal, alignment=2),
    )

    tabla = Table([[izquierda, centro, derecha]],
                  colWidths=[45 * mm, 72 * mm, 53 * mm])
    tabla.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, NEGRO),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
    ]))
    return tabla


def _linea_hospital(nota, etiqueta_tipo):
    """Hospital, ciudad y tipo repartidos en tres columnas.

    Con una sola linea de texto habria que separarlos con relleno invisible;
    una tabla los alinea de verdad.
    """
    celdas = [[
        Paragraph(f"<b>HOSPITAL:</b> {nota.hospital.upper()}", _normal),
        Paragraph(
            f"<b>CIUDAD:</b> {(nota.ciudad or 'CIUDAD DE MEXICO').upper()}",
            _normal,
        ),
        Paragraph(f"<b>TIPO:</b> {etiqueta_tipo.upper()}",
                  ParagraphStyle("tipo", parent=_normal, alignment=2)),
    ]]
    tabla = Table(celdas, colWidths=[80 * mm, 55 * mm, 35 * mm])
    tabla.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, 0), 0),
        ("RIGHTPADDING", (-1, 0), (-1, 0), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return tabla


def _tabla_conceptos(remision):
    """Conceptos de la remision: insumos o equipos, segun su tipo."""
    nota = remision.nota
    if remision.tipo == TipoRemision.INSUMOS:
        detalles = nota.detalles_insumo
    else:
        detalles = nota.detalles_equipo

    filas = [["CANTIDAD", "DESCRIPCION", "PRECIO UNITARIO", "IMPORTE"]]
    for d in detalles:
        filas.append([
            str(d.cantidad),
            Paragraph((d.descripcion or "").upper(), _normal),
            _moneda(d.precio_unitario),
            _moneda(d.importe),
        ])

    if not detalles:
        filas.append(["", Paragraph("Sin conceptos.", _normal), "", ""])

    tabla = Table(filas, colWidths=[20 * mm, 100 * mm, 25 * mm, 25 * mm],
                  repeatRows=1)
    tabla.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LINEABOVE", (0, 0), (-1, 0), 0.8, NEGRO),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, NEGRO),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#bbbbbb")),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tabla


def _totales(remision):
    filas = [
        ["SUBTOTAL", _moneda(remision.subtotal) or "$ 0.00"],
        ["IVA", _moneda(remision.iva) or "$ 0.00"],
        ["TOTAL", _moneda(remision.total) or "$ 0.00"],
    ]
    interna = Table(filas, colWidths=[30 * mm, 30 * mm])
    interna.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 1), 0.3, colors.HexColor("#dddddd")),
        ("FONTSIZE", (0, 2), (-1, 2), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))

    envoltura = Table([["", interna]], colWidths=[110 * mm, 60 * mm])
    envoltura.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return envoltura


def _recuadro_manual(remision):
    """Campos que el hospital llena a mano sobre el papel impreso.

    Paciente, habitacion, episodio y aseguradora no se capturan en el sistema:
    se escriben en el momento de la entrega, como en el formato anterior.
    """
    nota = remision.nota
    raya = "_" * 28

    izquierda = [
        f"<b>Fecha:</b> {nota.fecha_requerida.strftime('%d/%m/%Y')}",
        f"<b>Dr/a:</b> {nota.doctor or raya}",
        f"<b>Paciente:</b> {raya}",
        f"<b>Hab.:</b> {'_' * 10}",
        f"<b>Cirugia:</b> {nota.cirugia or raya}",
    ]
    derecha = [
        f"<b>Episodio:</b> {'_' * 18}",
        f"<b>Aseguradora:</b> {'_' * 18}",
        "",
        "<b>Sellos / Observaciones:</b>",
    ]

    celda_izq = Paragraph("<br/>".join(izquierda), _normal)
    celda_der = Paragraph("<br/>".join(derecha), _normal)

    tabla = Table([[celda_izq, celda_der]], colWidths=[85 * mm, 85 * mm])
    tabla.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, GRIS, None, (2, 2)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fafafa")),
    ]))
    return tabla


def _firmas(remision):
    tecnico = ""
    entrega = remision.entrega
    if entrega and entrega.tecnico:
        tecnico = entrega.tecnico.nombre

    filas = [
        ["Firma medico", "Firma enfermeria", "Tecnico"],
        ["", "", Paragraph(f'<font size="6">{tecnico}</font>', _centrado_chico)],
    ]
    tabla = Table(filas, colWidths=[56 * mm, 56 * mm, 56 * mm])
    tabla.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LINEABOVE", (0, 0), (-1, 0), 0.6, NEGRO),
        ("TOPPADDING", (0, 0), (-1, 0), 4),
    ]))
    return tabla


def _pie(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 6.5)
    canvas.setFillColor(GRIS)
    # La direccion ya va en el encabezado; aqui solo el contacto, como en el
    # formato del sistema anterior.
    telefonos = " / ".join(Empresa.TELEFONOS)
    canvas.drawCentredString(
        letter[0] / 2, 12 * mm,
        f"Contacto y programaciones: {telefonos}   -   {Empresa.CORREO}",
    )
    canvas.restoreState()


def generar_pdf_remision(remision, ruta):
    """Escribe el PDF de la remision en `ruta`. Devuelve la ruta."""
    documento = SimpleDocTemplate(
        str(ruta),
        pagesize=letter,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=15 * mm, bottomMargin=22 * mm,
        title=f"Remision {remision.folio}",
        author=remision.razon_social or "AVANT",
    )

    nota = remision.nota
    etiqueta_tipo = TipoRemision.ETIQUETAS.get(remision.tipo, remision.tipo)

    historia = [
        _encabezado(remision),
        Spacer(1, 8),
        _linea_hospital(nota, etiqueta_tipo),
        Spacer(1, 10),
        _tabla_conceptos(remision),
        Spacer(1, 8),
        _totales(remision),
        Spacer(1, 14),
        _recuadro_manual(remision),
        Spacer(1, 28),
        KeepTogether(_firmas(remision)),
    ]

    documento.build(historia, onFirstPage=_pie, onLaterPages=_pie)
    return ruta
