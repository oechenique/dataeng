// Panel lateral de contacto: "Escribime" abre el drawer y el mensaje va a una Lambda (Function URL) que lo
// manda por SES. Ver docs/contacto.md. La URL no es un secreto: la Lambda valida origen, tamaño y campos.
(function () {
  var ENDPOINT = 'https://egcdtzmsjb6ws2mjljupnfvzx40phmni.lambda-url.us-east-1.on.aws/';
  var LINKEDIN = 'https://www.linkedin.com/in/gaston-echenique/';
  var LIMITES = { nombre: 100, contacto: 200, asunto: 150, mensaje: 2000 };
  var OBLIGATORIOS = ['nombre', 'contacto', 'asunto'];
  var TEXTO_BOTON = 'Enviar mensaje';

  var PANEL_HTML =
    '<div class="contacto-fondo" data-cerrar></div>' +
    '<aside class="contacto-panel" role="dialog" aria-modal="true" aria-labelledby="contacto-titulo" tabindex="-1">' +
    '  <div class="contacto-cabecera">' +
    '    <h2 id="contacto-titulo">Escribime</h2>' +
    '    <button type="button" class="contacto-cerrar" data-cerrar aria-label="Cerrar">' +
    '      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>' +
    '    </button>' +
    '  </div>' +
    '  <p class="contacto-intro">Dejame tu mensaje y te respondo por mail o LinkedIn.</p>' +
    '  <form class="contacto-form" novalidate>' +
    '    <div class="contacto-campo">' +
    '      <label for="contacto-nombre">Nombre</label>' +
    '      <input id="contacto-nombre" name="nombre" type="text" maxlength="100" autocomplete="name" required aria-describedby="contacto-nombre-error">' +
    '      <span class="contacto-error" id="contacto-nombre-error"></span>' +
    '    </div>' +
    '    <div class="contacto-campo">' +
    '      <label for="contacto-contacto">Mail o LinkedIn</label>' +
    '      <input id="contacto-contacto" name="contacto" type="text" maxlength="200" autocomplete="email" required aria-describedby="contacto-contacto-ayuda contacto-contacto-error">' +
    '      <span class="contacto-ayuda" id="contacto-contacto-ayuda">Para poder responderte.</span>' +
    '      <span class="contacto-error" id="contacto-contacto-error"></span>' +
    '    </div>' +
    '    <div class="contacto-campo">' +
    '      <label for="contacto-asunto">Asunto</label>' +
    '      <input id="contacto-asunto" name="asunto" type="text" maxlength="150" required aria-describedby="contacto-asunto-error">' +
    '      <span class="contacto-error" id="contacto-asunto-error"></span>' +
    '    </div>' +
    '    <div class="contacto-campo">' +
    '      <label for="contacto-mensaje">Mensaje <span class="contacto-opcional">(opcional)</span></label>' +
    '      <textarea id="contacto-mensaje" name="mensaje" rows="6" maxlength="2000" aria-describedby="contacto-contador contacto-mensaje-error"></textarea>' +
    '      <span class="contacto-contador" id="contacto-contador">0 / 2000</span>' +
    '      <span class="contacto-error" id="contacto-mensaje-error"></span>' +
    '    </div>' +
    '    <div class="contacto-trampa" aria-hidden="true">' +
    '      <label for="contacto-website">No completar</label>' +
    '      <input id="contacto-website" name="website" type="text" tabindex="-1" autocomplete="off">' +
    '    </div>' +
    '    <button type="submit" class="btn btn-primary contacto-enviar">' + TEXTO_BOTON + '</button>' +
    '    <p class="contacto-estado" role="status" aria-live="polite"></p>' +
    '  </form>' +
    '  <p class="contacto-alternativa">¿Preferís LinkedIn? <a href="' + LINKEDIN + '" target="_blank" rel="noopener">Escribime por ahí →</a></p>' +
    '</aside>';

  var raiz, panel, form, boton, estado, contador, disparador;

  function enfocables() {
    return Array.prototype.filter.call(
      panel.querySelectorAll('a[href], button:not([disabled]), input:not([tabindex="-1"]), textarea'),
      function (el) { return el.offsetParent !== null; }
    );
  }

  function abrir() {
    disparador = document.activeElement;
    raiz.hidden = false;
    document.body.classList.add('contacto-abierto');
    // Forzar el layout para que la transición arranque desde fuera de pantalla.
    void panel.offsetWidth;
    raiz.classList.add('visible');
    form.elements.nombre.focus();
    document.addEventListener('keydown', teclado);
  }

  function cerrar() {
    raiz.classList.remove('visible');
    document.body.classList.remove('contacto-abierto');
    document.removeEventListener('keydown', teclado);
    setTimeout(function () { raiz.hidden = true; }, 250);
    if (disparador && disparador.focus) disparador.focus();
  }

  function teclado(e) {
    if (e.key === 'Escape') {
      e.preventDefault();
      cerrar();
      return;
    }
    if (e.key !== 'Tab') return;
    var lista = enfocables();
    if (!lista.length) return;
    var primero = lista[0];
    var ultimo = lista[lista.length - 1];
    if (e.shiftKey && (document.activeElement === primero || !panel.contains(document.activeElement))) {
      e.preventDefault();
      ultimo.focus();
    } else if (!e.shiftKey && (document.activeElement === ultimo || !panel.contains(document.activeElement))) {
      e.preventDefault();
      primero.focus();
    }
  }

  function marcarError(campo, mensaje) {
    var input = form.elements[campo];
    document.getElementById('contacto-' + campo + '-error').textContent = mensaje || '';
    if (mensaje) input.setAttribute('aria-invalid', 'true');
    else input.removeAttribute('aria-invalid');
  }

  function validar() {
    var primeroConError = null;
    Object.keys(LIMITES).forEach(function (campo) {
      var valor = form.elements[campo].value.trim();
      var mensaje = '';
      if (OBLIGATORIOS.indexOf(campo) !== -1 && !valor) mensaje = 'Este campo es obligatorio.';
      else if (valor.length > LIMITES[campo]) mensaje = 'Máximo ' + LIMITES[campo] + ' caracteres.';
      marcarError(campo, mensaje);
      if (mensaje && !primeroConError) primeroConError = form.elements[campo];
    });
    if (primeroConError) primeroConError.focus();
    return !primeroConError;
  }

  function mostrarEstado(tipo, html) {
    estado.className = 'contacto-estado' + (tipo ? ' ' + tipo : '');
    estado.innerHTML = html;
  }

  function enviar(e) {
    e.preventDefault();
    if (boton.disabled) return;
    mostrarEstado('', '');
    if (!validar()) return;

    var datos = { website: form.elements.website.value };
    Object.keys(LIMITES).forEach(function (campo) { datos[campo] = form.elements[campo].value.trim(); });

    boton.disabled = true;
    boton.textContent = 'Enviando…';

    var control = window.AbortController ? new AbortController() : null;
    var corte = control && setTimeout(function () { control.abort(); }, 10000);

    fetch(ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(datos),
      signal: control ? control.signal : undefined
    })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        form.reset();
        actualizarContador();
        boton.textContent = TEXTO_BOTON;
        mostrarEstado('ok', '¡Gracias! Te respondo pronto.');
      })
      .catch(function () {
        boton.textContent = TEXTO_BOTON;
        mostrarEstado('error', 'No se pudo enviar el mensaje. Probá de nuevo o <a href="' + LINKEDIN + '" target="_blank" rel="noopener">escribime por LinkedIn</a>.');
      })
      .then(function () {
        if (corte) clearTimeout(corte);
        boton.disabled = false;
      });
  }

  function actualizarContador() {
    contador.textContent = form.elements.mensaje.value.length + ' / ' + LIMITES.mensaje;
  }

  document.addEventListener('DOMContentLoaded', function () {
    var abrirBtn = document.getElementById('contacto-abrir');
    if (!abrirBtn) return;

    raiz = document.createElement('div');
    raiz.className = 'contacto';
    raiz.hidden = true;
    raiz.innerHTML = PANEL_HTML;
    document.body.appendChild(raiz);

    panel = raiz.querySelector('.contacto-panel');
    form = raiz.querySelector('.contacto-form');
    boton = raiz.querySelector('.contacto-enviar');
    estado = raiz.querySelector('.contacto-estado');
    contador = raiz.querySelector('.contacto-contador');

    abrirBtn.addEventListener('click', abrir);
    raiz.addEventListener('click', function (e) {
      if (e.target.closest('[data-cerrar]')) cerrar();
    });
    form.addEventListener('submit', enviar);
    form.elements.mensaje.addEventListener('input', actualizarContador);
    Object.keys(LIMITES).forEach(function (campo) {
      form.elements[campo].addEventListener('input', function () { marcarError(campo, ''); });
    });
  });
})();
