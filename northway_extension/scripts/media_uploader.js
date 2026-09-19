/**
 * Media Uploader - Handles media file attachment for broadcasts
 * Responsible for: attaching images/videos to WhatsApp messages
 */
class MediaUploader {
    /**
     * Attach media to the current WhatsApp chat
     * @param {object} engine 
     * @returns {Promise<boolean>} 
     */
    async attachMedia(engine) {
        if (!engine.media) return true;

        try {
            const arrayBuffer = await engine.media.arrayBuffer();
            const data = Array.from(new Uint8Array(arrayBuffer));
            const isImageOrVideo = engine.media.type.startsWith('image/') || engine.media.type.startsWith('video/');
            const kind = isImageOrVideo ? 'media' : 'document';

            window.postMessage({
                source: "NW_EXTENSION",
                type: "NW_ATTACH_FILE",
                payload: { kind, name: engine.media.name, mime: engine.media.type, data }
            }, "*");

            // Wait for preview (30s)
            for (let i = 0; i < 60; i++) {
                await new Promise(r => setTimeout(r, 500));
                // Would check for send button here
            }
            return true;
        } catch (e) {
            // toast("Erro ao anexar arquivo automaticamente.", "error");
            return false;
        }
    }
}

export default MediaUploader;