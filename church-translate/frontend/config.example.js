// Copy this file to config.js in the SAME folder when you host output.html
// yourself (phone page on GitHub Pages, Supabase Storage, or any static host).
//
// The laptop backend does not use this file. Opening http://127.0.0.1:8000/
// serves /config.js from the server, and that response never includes the
// service-role key.
//
// supabaseAnonKey is the public anon key or the sb_publishable_ key.
// Do not put the service_role or sb_secret key here.
window.CHURCH_TRANSLATE_CONFIG = {
  transport: "supabase",
  supabaseUrl: "https://YOUR-PROJECT.supabase.co",
  supabaseAnonKey: "YOUR-ANON-OR-PUBLISHABLE-KEY",
  runMode: "live",
  translationMode: "azure",
};
