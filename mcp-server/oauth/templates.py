"""HTML template for the OAuth authorize page with Firebase login."""


def render_authorize_page(
    firebase_api_key: str,
    firebase_auth_domain: str,
    firebase_project_id: str,
    client_id: str,
    redirect_uri: str,
    state: str,
    code_challenge: str,
    code_challenge_method: str,
    scope: str,
) -> str:
    """Render the Firebase login page for OAuth authorization."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign In - MCP Auth</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }}
        .container {{
            background: white;
            padding: 2rem;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            width: 100%;
            max-width: 400px;
        }}
        h1 {{
            font-size: 1.5rem;
            margin-bottom: 0.5rem;
            text-align: center;
        }}
        .subtitle {{
            color: #666;
            text-align: center;
            margin-bottom: 1.5rem;
            font-size: 0.9rem;
        }}
        .form-group {{
            margin-bottom: 1rem;
        }}
        label {{
            display: block;
            margin-bottom: 0.25rem;
            font-weight: 500;
            font-size: 0.9rem;
        }}
        input {{
            width: 100%;
            padding: 0.6rem;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 1rem;
        }}
        button {{
            width: 100%;
            padding: 0.7rem;
            border: none;
            border-radius: 6px;
            font-size: 1rem;
            cursor: pointer;
            margin-bottom: 0.75rem;
        }}
        .btn-google {{
            background: #4285f4;
            color: white;
        }}
        .btn-email {{
            background: #333;
            color: white;
        }}
        .divider {{
            text-align: center;
            color: #999;
            margin: 1rem 0;
            font-size: 0.85rem;
        }}
        .error {{
            background: #fee;
            color: #c00;
            padding: 0.5rem;
            border-radius: 6px;
            margin-bottom: 1rem;
            display: none;
            font-size: 0.85rem;
        }}
        .loading {{
            text-align: center;
            color: #666;
            display: none;
        }}
        .scope-info {{
            background: #f0f4ff;
            padding: 0.5rem 0.75rem;
            border-radius: 6px;
            margin-bottom: 1rem;
            font-size: 0.85rem;
            color: #444;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Sign In</h1>
        <p class="subtitle">Authorize access to MCP tools</p>

        <div class="scope-info" id="scopeInfo"></div>

        <div class="error" id="errorBox"></div>
        <div class="loading" id="loadingBox">Authorizing...</div>

        <button class="btn-google" id="googleBtn" onclick="signInWithGoogle()">
            Sign in with Google
        </button>

        <div class="divider">or</div>

        <form id="emailForm" onsubmit="signInWithEmail(event)">
            <div class="form-group">
                <label for="email">Email</label>
                <input type="email" id="email" required>
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" required>
            </div>
            <button type="submit" class="btn-email">Sign in with Email</button>
        </form>
    </div>

    <script src="https://www.gstatic.com/firebasejs/10.14.1/firebase-app-compat.js"></script>
    <script src="https://www.gstatic.com/firebasejs/10.14.1/firebase-auth-compat.js"></script>
    <script>
        // Firebase config injected from server
        const firebaseConfig = {{
            apiKey: "{firebase_api_key}",
            authDomain: "{firebase_auth_domain}",
            projectId: "{firebase_project_id}",
        }};

        // OAuth params embedded from server
        const oauthParams = {{
            client_id: "{client_id}",
            redirect_uri: "{redirect_uri}",
            state: "{state}",
            code_challenge: "{code_challenge}",
            code_challenge_method: "{code_challenge_method}",
            scope: "{scope}",
        }};

        firebase.initializeApp(firebaseConfig);
        const auth = firebase.auth();

        // Show requested scopes
        const scopeEl = document.getElementById("scopeInfo");
        if (oauthParams.scope) {{
            scopeEl.textContent = "Requested access: " + oauthParams.scope;
        }} else {{
            scopeEl.style.display = "none";
        }}

        function showError(msg) {{
            const box = document.getElementById("errorBox");
            box.textContent = msg;
            box.style.display = "block";
            document.getElementById("loadingBox").style.display = "none";
        }}

        function showLoading() {{
            document.getElementById("loadingBox").style.display = "block";
            document.getElementById("errorBox").style.display = "none";
            document.getElementById("googleBtn").disabled = true;
            document.getElementById("emailForm").querySelectorAll("button, input").forEach(
                el => el.disabled = true
            );
        }}

        async function handleAuthResult(user) {{
            showLoading();
            try {{
                const idToken = await user.getIdToken();
                const resp = await fetch("/authorize/callback", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{
                        firebase_id_token: idToken,
                        client_id: oauthParams.client_id,
                        redirect_uri: oauthParams.redirect_uri,
                        state: oauthParams.state,
                        code_challenge: oauthParams.code_challenge,
                        code_challenge_method: oauthParams.code_challenge_method,
                    }}),
                }});
                if (!resp.ok) {{
                    const err = await resp.json();
                    showError(err.error || "Authorization failed");
                    return;
                }}
                const data = await resp.json();
                window.location.href = data.redirect_url;
            }} catch (e) {{
                showError("Network error: " + e.message);
            }}
        }}

        async function signInWithGoogle() {{
            try {{
                const provider = new firebase.auth.GoogleAuthProvider();
                const result = await auth.signInWithPopup(provider);
                await handleAuthResult(result.user);
            }} catch (e) {{
                showError(e.message);
            }}
        }}

        async function signInWithEmail(event) {{
            event.preventDefault();
            const email = document.getElementById("email").value;
            const password = document.getElementById("password").value;
            try {{
                const result = await auth.signInWithEmailAndPassword(email, password);
                await handleAuthResult(result.user);
            }} catch (e) {{
                showError(e.message);
            }}
        }}
    </script>
</body>
</html>"""
