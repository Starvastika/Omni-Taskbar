.pragma library
var cached = null
function rings(serialized) {
    if (cached === null) cached = JSON.parse(serialized)
    return cached
}
