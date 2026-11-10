/* Card share page.
 *
 * One card, one screen, built for a phone: hand the image to Instagram or
 * Snapchat in as few taps as the platforms allow. Neither app lets a web page
 * post a story by itself, so the Instagram route is the system share sheet with
 * the image attached (Instagram is one tap away, "Your Story" the next), and the
 * Snapchat route is Snap's own Creative Kit, which deep links into Snapchat with
 * the card attached as a sticker and the athlete's page as the link.
 */

// @ts-nocheck
(function () {
    const SNAP_SDK_ID = 'snapkit-creative-kit-sdk';
    const SNAP_SDK_SRC = 'https://sdk.snapkit.com/js/v1/create.js';

    function loadSnapSdk() {
        if (document.getElementById(SNAP_SDK_ID)) return;
        const first = document.getElementsByTagName('script')[0];
        const script = document.createElement('script');
        script.id = SNAP_SDK_ID;
        script.src = SNAP_SDK_SRC;
        script.async = true;
        first.parentNode.insertBefore(script, first);
    }

    // Snap's SDK wires any element with this class and a data-share-url; the
    // misspelling is theirs.
    function initSnapButtons(elements) {
        const kit = window.snap && window.snap.creativekit;
        if (!kit) return false;
        const init = kit.initalizeShareButtons || kit.initializeShareButtons;
        if (typeof init !== 'function') return false;
        init(elements);
        return true;
    }

    window.TrackInsightsShare = {loadSnapSdk, initSnapButtons};

    document.addEventListener('DOMContentLoaded', () => {
        const page = document.querySelector('.card-share-page');
        if (!page) return;
        const pngUrl = page.dataset.pngUrl;
        const shareUrl = page.dataset.shareUrl;
        const title = page.dataset.title;
        const filename = page.dataset.downloadName;
        const status = document.getElementById('card-share-status');
        const setStatus = message => { status.textContent = message; };
        const instagramButton = document.getElementById('card-share-instagram');
        const snapchatButton = document.getElementById('card-share-snapchat');
        const moreButton = document.getElementById('card-share-more');
        const isMobile = Boolean(navigator.userAgentData?.mobile || /Android|iPhone|iPad|iPod/i.test(navigator.userAgent)
            || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1));

        let imageFile = null;
        const imageReady = fetch(pngUrl).then(response => {
            if (!response.ok) throw new Error(`Card image request failed (${response.status}).`);
            return response.blob();
        }).then(blob => {
            imageFile = typeof File === 'function' ? new File([blob], filename, {type: 'image/png'}) : null;
        }).catch(error => {
            console.warn('Card image unavailable:', error);
            setStatus('The card image is still rendering. Try again in a moment.');
        });

        const canShareFile = () => Boolean(imageFile && navigator.share && navigator.canShare
            && navigator.canShare({files: [imageFile]}));

        async function shareImage(platform) {
            await imageReady;
            if (canShareFile()) {
                try {
                    await navigator.share({files: [imageFile], title});
                    setStatus(platform
                        ? `Pick ${platform} in the sheet, then ${platform === 'Instagram' ? 'Your Story' : 'Story'}.`
                        : 'Shared.');
                } catch (error) {
                    if (error.name !== 'AbortError') console.warn('Share failed', error);
                    setStatus(error.name === 'AbortError' ? 'Sharing canceled.' : 'Sharing is not available here. Save the image instead.');
                }
                return true;
            }
            return false;
        }

        instagramButton.addEventListener('click', async () => {
            instagramButton.disabled = true;
            try {
                if (await shareImage('Instagram')) return;
                if (isMobile) {
                    // No file sharing in this browser: save the card, then open
                    // Instagram on its story camera to pick it from the roll.
                    document.getElementById('card-share-download').click();
                    setStatus('Card saved. Opening Instagram: pick it from your files or camera roll.');
                    setTimeout(() => { window.location.href = 'instagram://story-camera'; }, 700);
                    return;
                }
                setStatus('Instagram stories can only be posted from a phone. Open this page on your phone and tap again.');
            } finally {
                instagramButton.disabled = false;
            }
        });

        // Snapchat: Creative Kit when its SDK is available, the share sheet otherwise.
        loadSnapSdk();
        const snapAnchor = document.getElementById('snapchat-share-anchor');
        let snapKitButton = null;
        function ensureSnapKitButton() {
            if (snapKitButton) return snapKitButton;
            const node = document.createElement('div');
            node.className = 'snapchat-share-button';
            node.setAttribute('data-share-url', shareUrl);
            snapAnchor.appendChild(node);
            if (!initSnapButtons([node])) {
                node.remove();
                return null;
            }
            snapKitButton = node;
            return node;
        }
        window.snapKitInit = () => { ensureSnapKitButton(); };
        if (window.snap && window.snap.creativekit) ensureSnapKitButton();

        snapchatButton.addEventListener('click', async () => {
            const kitButton = ensureSnapKitButton();
            if (kitButton && /^https:/.test(shareUrl)) {
                // Snap's handler is on this element; a click inside our tap
                // keeps the user activation it needs to open the app.
                kitButton.click();
                setStatus(isMobile ? 'Opening Snapchat with your card.' : 'Scan the Snapcode with Snapchat to open the card there.');
                return;
            }
            if (await shareImage('Snapchat')) return;
            setStatus('Snapchat sharing works from a phone. Open this page on your phone and tap again.');
        });

        const downloadLink = document.getElementById('card-share-download');
        if (isMobile) {
            downloadLink.querySelector('span').textContent = 'Save to Photos';
        }
        downloadLink.addEventListener('click', event => {
            // On a phone the share sheet's Save Image puts the card in Photos;
            // the plain download would land in Files. The share call has to
            // run straight from the tap, so the image must already be fetched.
            if (!canShareFile()) return;
            event.preventDefault();
            navigator.share({files: [imageFile], title}).catch(error => {
                if (error.name === 'AbortError') { setStatus('Saving canceled.'); return; }
                console.warn('Share sheet failed', error);
                window.location.href = downloadLink.href;
            });
            setStatus('Tap Save Image in the sheet to add the card to your Photos.');
        });

        moreButton.addEventListener('click', async () => {
            if (await shareImage(null)) return;
            if (navigator.share) {
                try {
                    await navigator.share({title, url: shareUrl});
                    setStatus('Shared.');
                    return;
                } catch (error) {
                    if (error.name === 'AbortError') { setStatus('Sharing canceled.'); return; }
                }
            }
            try {
                await navigator.clipboard.writeText(shareUrl);
                setStatus('Link copied.');
            } catch {
                setStatus(`Copy this link: ${shareUrl}`);
            }
        });
    });
})();
