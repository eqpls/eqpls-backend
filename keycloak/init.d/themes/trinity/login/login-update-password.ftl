<#import "template.ftl" as layout>
<#import "password-commons.ftl" as passwordCommons>
<@layout.registrationLayout displayMessage=!messagesPerField.existsError('password','password-confirm'); section>
    <#if section = "header">
        <#--  ${msg("updatePasswordTitle")}  -->
        <script>
            function toggleNewPassword() {
                var x = document.getElementById("password-new");
                var v = document.getElementById("password-new-vi");
                if (x.type === "password") {
                    x.type = "text";
                    v.src = "${url.resourcesPath}/img/eye.png";
                } else {
                    x.type = "password";
                    v.src = "${url.resourcesPath}/img/eye-off.png";
                }
            }
             function toggleConfirmPassword() {
                var x = document.getElementById("password-confirm");
                var v = document.getElementById("password-confirm-vi");
                if (x.type === "password") {
                    x.type = "text";
                    v.src = "${url.resourcesPath}/img/eye.png";
                } else {
                    x.type = "password";
                    v.src = "${url.resourcesPath}/img/eye-off.png";
                }
            }
        </script>
    <#elseif section = "logo">
      <div class="logo-container">
          <img class="logo" src="${url.resourcesPath}/img/logo.svg" alt="trinity-logo" />
      </div>
    <#elseif section = "form">
      <div class="form-container">
        <form id="kc-passwd-update-form" class="form" action="${url.loginAction}" method="post">
          <label for="password-new" class="form-label">${msg("passwordNew")}</label>
          <div class="password-box">
            <input type="password" id="password-new" name="password-new" class="password-input"
                  autofocus autocomplete="new-password"
                  aria-invalid="<#if messagesPerField.existsError('password','password-confirm')>true</#if>"
             />
           <label class="visibility" id="v" onclick="toggleNewPassword()"><img id="password-new-vi" src="${url.resourcesPath}/img/eye-off.png"></label>
          </div>       
          <#if messagesPerField.existsError('password')>
              <span id="input-error-password" class="${properties.kcInputErrorMessageClass!}" aria-live="polite">
                  ${kcSanitize(messagesPerField.get('password'))?no_esc}
              </span>
          </#if>
          <label for="password-confirm" class="form-label">${msg("passwordConfirm")}</label>
          <div class="password-box">
            <input type="password" id="password-confirm" name="password-confirm"
                class="password-input"
                autocomplete="new-password"
                aria-invalid="<#if messagesPerField.existsError('password-confirm')>true</#if>"
            />
            <label class="visibility" id="v" onclick="toggleConfirmPassword()"><img id="password-confirm-vi" src="${url.resourcesPath}/img/eye-off.png"></label>
          </div>
            <@passwordCommons.logoutOtherSessions/>
            <#if isAppInitiatedAction??>
                <input class="${properties.kcButtonClass!} ${properties.kcButtonPrimaryClass!} ${properties.kcButtonLargeClass!}" type="submit" value="${msg('doSubmit')}" />
                <button class="submit-button" type="submit" name="cancel-aia" value="true">${msg("doCancel")}</button>
            <#else>
                <input class="${properties.kcButtonClass!} ${properties.kcButtonPrimaryClass!} ${properties.kcButtonBlockClass!} ${properties.kcButtonLargeClass!} submit-button" type="submit" value="${msg('doSubmit')}" />
            </#if>
        </form>
      </div>
      <#if messagesPerField.existsError('password-confirm')>
        <div class="alert-container">
          <div class="alert alert-${message.type}">
              <#--  <#if message.type = 'success'><span class="${properties.kcFeedbackSuccessIcon!}"></span></#if>
              <#if message.type = 'warning'><span class="${properties.kcFeedbackWarningIcon!}"></span></#if>
              <#if message.type = 'error'><span class="${properties.kcFeedbackErrorIcon!}"></span></#if>
              <#if message.type = 'info'><span class="${properties.kcFeedbackInfoIcon!}"></span></#if>  -->
              <div class="message-icon-box"><img class="message-warning-icon" src="${url.resourcesPath}/img/warning.svg" alt="warning" /></div>
              <div id="input-error-password-confirm" class="message-text" aria-live="polite">
                ${kcSanitize(messagesPerField.get('password-confirm'))?no_esc}
              </div>
          </div>
        </div>
        
      </#if>
      <script type="module" src="${url.resourcesPath}/js/passwordVisibility.js"></script>
    <#elseif section = "footer">
        <div class="footer-container">
            <div class="application-container">
                <p class="application-name">
                    ${msg("applicationName")}
                </p>
                <p class="application-date">
                    ${msg("applicationDate")}
                </p>
            </div>
            <p class="version">
                ver ${msg("version")}
            </p>
        </div>
    <#elseif section = "image">
      <div class="image-container">
          <img class="image" src="${url.resourcesPath}/img/trinity.webp" alt="trinity" />
      </div>
    </#if>
</@layout.registrationLayout>