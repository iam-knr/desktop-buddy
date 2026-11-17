import QtQuick
import org.kde.plasma.plasma5support as P5Support

// Talks to ~/.local/share/summit/summitctl.py. All user text is URL-encoded
// (and ' escaped) before it touches the shell.
Item {
    id: store
    readonly property string ctl: "python3 \"$HOME/.local/share/summit/summitctl.py\""
    property var callbacks: ({})
    property int seq: 0

    function enc(s) {
        return "'" + encodeURIComponent(s).replace(/'/g, "%27") + "'"
    }
    function run(args, cb) {
        seq += 1
        var cmd = ctl + " " + args + " #" + seq   // the counter keeps each call unique
        callbacks[cmd] = cb || null
        ds.connectSource(cmd)
    }
    function get(kind, cb) {
        run("get " + kind, function (out) {
            try { cb(JSON.parse(out)) } catch (e) { console.warn("summit: bad data for", kind, out) }
        })
    }
    function json(obj) { return enc(JSON.stringify(obj)) }

    P5Support.DataSource {
        id: ds
        engine: "executable"
        connectedSources: []
        onNewData: function (source, data) {
            var cb = store.callbacks[source]
            delete store.callbacks[source]
            disconnectSource(source)
            if (data["exit code"] !== 0 && data["stderr"])
                console.warn("summit:", data["stderr"])
            if (cb) cb(data["stdout"] || "")
        }
    }
}
