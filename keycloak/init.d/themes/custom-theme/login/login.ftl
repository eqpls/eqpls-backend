<#import "template.ftl" as layout>
<#--  <#assign displayInfo = {"displayMessage": true}>  -->
<@layout.registrationLayout displayInfo=social.displayInfo; section>
    <#if section = "title">
        ${msg("loginTitle",(realm.displayName!''))}
    <#elseif section = "header">
        <link href="https://fonts.googleapis.com/css?family=Muli" rel="stylesheet"/>
        <link href="${url.resourcesPath}/img/favicon.png" rel="icon"/>
        <script>
            function togglePassword() {
                var x = document.getElementById("password");
                var v = document.getElementById("vi");
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
            <div class="form-label">Login</div>
            <#if realm.password>
            <form id="kc-form-login" class="form" onsubmit="return true;" action="${url.loginAction}" method="post">
                <input id="username" class="id-input" placeholder="${msg('username')}" type="text" name="username" tabindex="1">
                <div class="password-box">
                    <input id="password" class="password-input" placeholder="${msg('password')}" type="password" name="password" tabindex="2">
                    <label class="visibility" id="v" onclick="togglePassword()"><img id="vi" src="${url.resourcesPath}/img/eye-off.png"></label>
                </div>
                <input class="submit-button" type="submit" value="${msg('doLogIn')}" tabindex="3">
            </form>
            </#if>
         </div>
        <#--  <div>
            <p class="copyright">&copy; ${msg("copyright", "${.now?string('yyyy')}")}</p>
        </div>  -->
    <#elseif section = "socialProviders">
        <#if social.providers??>
            <p class="para">${msg("selectAlternative")}</p>
            <div id="social-providers">
                <#list social.providers as p>
                <input class="social-link-style" type="button" onclick="location.href='${p.loginUrl}';" value="${p.displayName}"/>
                </#list>
            </div>
        </#if>
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
