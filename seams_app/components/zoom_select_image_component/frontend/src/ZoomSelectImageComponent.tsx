import {
  Streamlit,
  StreamlitComponentBase,
  withStreamlitConnection,
} from 'streamlit-component-lib'
import React, { ReactNode } from 'react'

import ZoomRectangleManager, { Rectangle } from './components/ZoomRectangleManager'

/**
 * This is a React-based component template. The `render()` function is called
 * automatically when your component should be re-rendered.
 */

interface State {
  rectangles: Rectangle[];
}

class MyComponent extends StreamlitComponentBase<State> {
  public state = { rectangles: [] }

  public render = (): ReactNode => {
    return (
      <ZoomRectangleManager
        // the component is rendered in an iframe which may be on a different host than the streamlit server
        // since image_url points to an image on the streamlit server, we need to qualify the url with the host of
        // the streamlit server (i.e. document.referrer)
        imageUrl={new URL(this.props.args['image_url'], document.referrer).toString()}
        rectangles={this.state.rectangles}
        setRectangles={this.setRectangles}
        originalRectangle={{ width: this.props.args['rectangle_width'], height: this.props.args['rectangle_height'] }}
      />
    );
  }

  private setRectangles = (rectangles: Rectangle[]): void => {
    this.setState(
      { rectangles },
      () => Streamlit.setComponentValue(this.state.rectangles)
    );
  }
}

// 'withStreamlitConnection' is a wrapper function. It bootstraps the
// connection between your component and the Streamlit app, and handles
// passing arguments from Python -> Component.
export default withStreamlitConnection(MyComponent);
