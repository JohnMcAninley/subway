// Reading files out of a zip in the browser, with its own DecompressionStream: just
// enough for the MTA's schedule zips (stored or deflated, and under 4 GB).

const END = 0x06054b50, CENTRAL = 0x02014b50, LOCAL = 0x04034b50

// The files in a zip's bytes (a Uint8Array): name -> { size, stream() }, where stream()
// gives the file's text as a ReadableStream of strings.
export function entries(bytes) {
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
    // The end record is last, after a comment of up to 64 KB.
    let end = bytes.length - 22
    while (end >= Math.max(0, bytes.length - 22 - 0xffff) && view.getUint32(end, true) !== END)
        end--
    if (end < 0 || view.getUint32(end, true) !== END)
        throw new Error("Not a zip")

    const files = {}
    let at = view.getUint32(end + 16, true)
    for (let count = view.getUint16(end + 10, true); count > 0; count--) {
        if (view.getUint32(at, true) !== CENTRAL)
            throw new Error("Not a zip: bad central directory")
        const method = view.getUint16(at + 10, true)
        const compressed = view.getUint32(at + 20, true), size = view.getUint32(at + 24, true)
        const nameLength = view.getUint16(at + 28, true)
        const extraLength = view.getUint16(at + 30, true), commentLength = view.getUint16(at + 32, true)
        const local = view.getUint32(at + 42, true)
        const name = new TextDecoder().decode(bytes.subarray(at + 46, at + 46 + nameLength))
        at += 46 + nameLength + extraLength + commentLength

        files[name] = {
            size,
            stream() {
                if (view.getUint32(local, true) !== LOCAL)
                    throw new Error("Not a zip: bad header for " + name)
                const start = local + 30 + view.getUint16(local + 26, true) + view.getUint16(local + 28, true)
                let data = new Blob([bytes.subarray(start, start + compressed)]).stream()
                if (method === 8)
                    data = data.pipeThrough(new DecompressionStream("deflate-raw"))
                else if (method !== 0)
                    throw new Error("Can't unzip " + name + ": compression method " + method)
                return data.pipeThrough(new TextDecoderStream())
            },
        }
    }
    return files
}

// The lines of a stream of text, without their line endings, a chunk's worth at a time: for
// await (const batch of lines(stream)) for (const line of batch). Line by line, a file of
// millions of them would spend more time waiting its turn than being read.
export async function* lines(stream) {
    let rest = ""
    const reader = stream.getReader()
    for (;;) {
        const { done, value } = await reader.read()
        if (done)
            break
        const parts = (rest + value).split("\n")
        rest = parts.pop()
        yield parts.map(line => line.endsWith("\r") ? line.slice(0, -1) : line)
    }
    if (rest)
        yield [rest.endsWith("\r") ? rest.slice(0, -1) : rest]
}

// A line of CSV as its fields, with quoted ones unquoted.
export function csvFields(line) {
    if (!line.includes('"'))
        return line.split(",")
    const found = []
    let field = "", quoted = false
    for (let i = 0; i < line.length; i++) {
        const c = line[i]
        if (quoted) {
            if (c === '"' && line[i + 1] === '"') {
                field += '"'
                i++
            } else if (c === '"') {
                quoted = false
            } else {
                field += c
            }
        } else if (c === '"') {
            quoted = true
        } else if (c === ",") {
            found.push(field)
            field = ""
        } else {
            field += c
        }
    }
    found.push(field)
    return found
}

// Every row of a CSV file's text stream, as an object by its header's names.
export async function csvRows(stream) {
    let header = null
    const rows = []
    for await (const batch of lines(stream)) {
        for (const line of batch) {
            const values = csvFields(line)
            if (header === null) {
                header = values
            } else if (line !== "") {
                const row = {}
                header.forEach((name, i) => row[name] = values[i] === undefined ? "" : values[i])
                rows.push(row)
            }
        }
    }
    return rows
}
