import { Streamlit } from "streamlit-component-lib"
import React, { CSSProperties, useEffect } from "react"

export interface Rectangle {
  // position and width of the rectangle, expressed in pixels
  left: number;
  top: number;
  width: number;
  height: number;

  scale: number;

  // this is the point that the rectangle is zoomed around
  // it is usually the center of the rectangle, but not when the rectangle is close to the edge of its container
  // hence we have to keep track of this point separately so that we can apply the zoom transform properly
  focalPoint: { x: number, y: number };

  shouldAnnotate: boolean;
}

interface CursorPosition {
  x: number;
  y: number;
}

interface OriginalRectangleDimensions {
  width: number;
  height: number;
}

interface ZoomRectangleManagerProps {
  imageUrl: string;
  rectangles: Rectangle[];
  setRectangles(rectangles: Rectangle[]): void;
  originalRectangle: OriginalRectangleDimensions,
}

// Changes the top/left coordinates and width/height of a rectangle so that it's fully contained within the
// rectangle [0, max.x] x [0, max.y]
function clamp(rectangle: Rectangle, max: { x: number, y: number }) {
  if (rectangle.left < 0) {
    rectangle.width = rectangle.width + rectangle.left;
    rectangle.left = 0;
  }

  if (rectangle.top < 0) {
    rectangle.height = rectangle.height + rectangle.top;
    rectangle.top = 0;
  }

  if (rectangle.left + rectangle.width > max.x) {
    rectangle.width = max.x - rectangle.left;
  }

  if (rectangle.top + rectangle.height > max.y) {
    rectangle.height = max.y - rectangle.top;
  }
}

export default function ZoomRectangleManager(props: ZoomRectangleManagerProps) {
  const { rectangles, setRectangles, originalRectangle } = props;

  const addRectangle = (rectangle: Rectangle) => setRectangles([...rectangles, rectangle]);
  const removeRectangle = (rectangle: Rectangle) => setRectangles(rectangles.filter(r => r !== rectangle));
  const updateRectangle = (rectangle: Rectangle, newRectangle: Rectangle) =>
    setRectangles(rectangles.map(r => r === rectangle ? newRectangle : r));

  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const imageRef = React.useRef<HTMLImageElement | null>(null);

  // Hack: React's event handlign system does something funny to wheel events which causes the whole page to scroll when
  // using the wheel to zoom unless preventDefault() is called directly on the event, sidestepping the React event
  // handling entirely
  // see https://stackoverflow.com/questions/57358640/cancel-wheel-event-with-e-preventdefault-in-react-event-bubbling
  useEffect(() => {
    containerRef.current?.addEventListener("wheel", (e) => { e.preventDefault(); })
  }, [containerRef.current]);

  const [cursorPosition, setCursorPosition] = React.useState<CursorPosition | null>(null)
  const [scale, setScale] = React.useState(1);

  const handleMouseMove = React.useCallback((event: React.MouseEvent<HTMLDivElement>) => {
    const boundingRect = event.currentTarget.getBoundingClientRect();

    // calculate cursor position relative to the event listener
    const x = event.clientX - boundingRect.left;
    const y = event.clientY - boundingRect.top;

    setCursorPosition({ x, y });
  }, [setCursorPosition]);

  const handleMouseLeave = React.useCallback(() => {
    setCursorPosition(null);
  }, [setCursorPosition]);

  const handleWheel = React.useCallback((event: React.WheelEvent<HTMLDivElement>) => {
    // Possible improvement: use a library to do this in a better way. This causes unnecessarily many rerenders.
    // use the log2 to speed up the zoom on higher zoom levels (we want 4x->8x to take as much scrolling as 2x->4x)
    let newScale = scale + Math.log2(scale + 0.1) * 0.02 * event.deltaY;
    if (newScale < 1) {
      newScale = 1;
    }
    if (newScale > 32) {
      newScale = 32;
    }
    setScale(newScale);
  }, [scale, setScale]);

  return (
    <div
      style={{ position: 'relative', overflow: 'hidden' }}
      ref={containerRef}
    >
      <div
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        onWheel={handleWheel}
      >
        <img
          ref={imageRef}
          alt=''
          src={props.imageUrl}
          style={{ userSelect: 'none', maxWidth: '100%' }}
          // Necessary because the component is wrapped in an iframe and its height needs to manually updated by
          // Streamlit once all content has been loaded.
          onLoad={() => Streamlit.setFrameHeight()}
        />

        {(cursorPosition !== null && imageRef.current !== null) &&
          <CursorRectangle
            cursorPosition={cursorPosition}
            scale={scale}
            imageElement={imageRef.current}
            originalRectangle={originalRectangle}
            addRectangle={addRectangle}
          />
        }
      </div>

      {rectangles.map((r, i) =>
        (imageRef.current !== null) &&
          <FixedRectangle
            key={i}
            rectangle={r}
            imageElement={imageRef.current}
            originalRectangle={originalRectangle}
            removeRectangle={removeRectangle}
            updateRectangle={updateRectangle}
          />
      )}
    </div>
  );
}

interface PlacedRectangleProps {
  rectangle: Rectangle;
  imageElement: HTMLImageElement;
  originalRectangle: OriginalRectangleDimensions,
  removeRectangle(rectangle: Rectangle): void;
  updateRectangle(rectangle: Rectangle, newRectangle: Rectangle): void;
}

function FixedRectangle({ rectangle, imageElement, originalRectangle, removeRectangle, updateRectangle }: PlacedRectangleProps) {
  const closeButtonStyle: CSSProperties = {
    position: 'absolute',
    top: '4px',
    right: '4px',
    cursor: 'pointer',
    lineHeight: '0.7rem',
    fontSize: '1rem',
    color: '#EEE',
    textShadow: '1px 1px black',
  };

  return (
    <ZoomedRectangle rectangle={rectangle} imageElement={imageElement} originalRectangle={originalRectangle}>
      <div style={closeButtonStyle} onClick={() => removeRectangle(rectangle)}>×</div>

      <input
        type='checkbox'
        style={{ position: 'absolute', bottom: '5px', right: '5px' }}
        checked={rectangle.shouldAnnotate}
        onChange={(e) => updateRectangle(rectangle, { ...rectangle, shouldAnnotate: e.currentTarget.checked })}
      />
    </ZoomedRectangle>
  );
}

interface CursorRectangleProps {
  cursorPosition: CursorPosition;
  scale: number;
  originalRectangle: OriginalRectangleDimensions;
  imageElement: HTMLImageElement;
  addRectangle(rectangle: Rectangle): void;
}

function CursorRectangle({ cursorPosition, scale, imageElement, originalRectangle, addRectangle }: CursorRectangleProps) {
  // The pixels of the image are usually not rendered 1:1 on the screen.
  // We prefer to store all rectangles as image coordinates, but this does
  // This is the number of screen pixels per image pixel.
  const imagePixelRatio = imageElement.clientWidth / imageElement.naturalWidth;

  // We want the rectangle to have the cursor as focal point
  // cursorPsoition is given in screen coordinates, so we change into image coordinates.
  // Example: if the image is 1800x900 pixels, but rendered as 900x450 on the screen and the cursor is at
  // (300, 400) relative the top left corner of image, we'd like the rectangle to be centered on (600, 800)
  const focalPoint = { x: cursorPosition.x / imagePixelRatio, y: cursorPosition.y / imagePixelRatio }

  // When we zoom, the rectangle should cover a smaller section of the image.
  // Accordingly we reduce the width and height as we zoom in.
  const width = originalRectangle.width / scale;
  const height = originalRectangle.height / scale;

  const left = focalPoint.x - width / 2
  const top = focalPoint.y - height / 2

  const cursorRectangle = { left, top, width, height, scale, focalPoint, shouldAnnotate: false };

  // ensure that the rectangle is contained within the image
  clamp(cursorRectangle, { x: imageElement.naturalWidth, y: imageElement.naturalHeight })

  return (
    <ZoomedRectangle
      rectangle={cursorRectangle}
      imageElement={imageElement}
      style={{ cursor: 'none' }}
      originalRectangle={originalRectangle}
      onClick={() => addRectangle(cursorRectangle)}
    />
  )
}

interface ZoomedRectangleProps {
  rectangle: Rectangle;
  imageElement: HTMLImageElement;
  style?: CSSProperties;
  originalRectangle: OriginalRectangleDimensions;
  onClick?: React.MouseEventHandler<HTMLDivElement>;
  children?: React.ReactNode,
}

function ZoomedRectangle({ rectangle, imageElement, style: extraStyles, originalRectangle, onClick, children }: ZoomedRectangleProps) {
  if (imageElement === null)
    return null;

  const imagePixelRatio = imageElement.clientWidth / imageElement.naturalWidth;

  // something like would be the easiest and clearest way to do what we are doing below
  // the problem is that it has very bad performance; browsers seem to be a lot faster at moving and rescaling
  // images than repeatedly plotting them to a canvas

  // const canvasRef = useRef<HTMLCanvasElement | null>(null);
  // useEffect(() => {
  //   if (canvasRef.current === null)
  //     return;

  //   const drawingContext = canvasRef.current.getContext('2d');
  //   drawingContext?.drawImage(
  //     imageElement,
  //     rectangle.left,
  //     rectangle.top,
  //     rectangle.width,
  //     rectangle.height,
  //     0,
  //     0,
  //     screenRectangle.width,
  //     screenRectangle.height,
  //   );

  // }, [rectangle]);

  // This is the rectangle that is rendered onto the screen, in screen coordinates
  const screenRectangle = {
    left: (rectangle.focalPoint.x - originalRectangle.width/2) * imagePixelRatio,
    top: (rectangle.focalPoint.y - originalRectangle.height/2) * imagePixelRatio,
    width: originalRectangle.width * imagePixelRatio,
    height: originalRectangle.height * imagePixelRatio,
    focalPoint: { x: rectangle.focalPoint.x * imagePixelRatio, y: rectangle.focalPoint.y * imagePixelRatio },
    shouldAnnotate: false,
    scale: 1,
  }
  clamp(screenRectangle, { x: imageElement.clientWidth, y: imageElement.clientHeight })

  // this is the imagePixelRatio (number of screen pixels per image pixel) of the magnified image that is shown inside
  // the rectangle
  const scale = rectangle.scale * imagePixelRatio;

  const style: CSSProperties = {
    position: 'absolute',
    left: screenRectangle.left,
    top: screenRectangle.top,
    width: screenRectangle.width,
    height: screenRectangle.height,
    backgroundImage: `url(${imageElement.src})`,
    // scale the image up/down
    backgroundSize: `${scale * imageElement.naturalWidth}px ${scale * imageElement.naturalHeight}px`,
    // this translation is done after the scaling above, so we need to consider the scaling
    // ensures that the image pixel (rectangle.left, rectangle.top) are in the top left corner of the rectangle rendered
    // onto the screen
    backgroundPosition: `${-rectangle.left * scale}px ${-rectangle.top * scale}px`,
    backgroundRepeat: 'no-repeat',
    backgroundOrigin: 'border-box',
    boxShadow: 'white 0 0 4px',
    overflow: 'hidden',
    ...extraStyles,
  };

  return (
    <div style={style} onClick={onClick}>
      {children}
    </div>
  );
}
