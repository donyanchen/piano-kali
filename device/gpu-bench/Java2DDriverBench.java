import java.awt.*;
import java.awt.image.*;
import java.lang.management.ManagementFactory;
import com.sun.management.OperatingSystemMXBean;

// Supplemental Swing/Java2D-like paint workload, not a Burp application benchmark.
public class Java2DDriverBench {
  public static void main(String[] args) throws Exception {
    GraphicsConfiguration gc=GraphicsEnvironment.getLocalGraphicsEnvironment()
      .getDefaultScreenDevice().getDefaultConfiguration();
    if(!gc.getClass().getName().contains("GLX")) throw new RuntimeException("OpenGL pipeline unavailable");
    VolatileImage image=gc.createCompatibleVolatileImage(1600,1000,Transparency.OPAQUE);
    image.validate(gc);
    if(!image.getCapabilities().isAccelerated()) throw new RuntimeException("Image acceleration unavailable");
    OperatingSystemMXBean bean=(OperatingSystemMXBean)ManagementFactory.getOperatingSystemMXBean();
    Font font=new Font(Font.SANS_SERIF,Font.PLAIN,18);
    System.out.println("{\"graphics_config\":\""+gc.getClass().getName()+"\",\"frames_per_pass\":120,\"passes\":[");
    for(int pass=0;pass<5;pass++) {
      long cpu=bean.getProcessCpuTime(),start=System.nanoTime();
      for(int frame=0;frame<120;frame++) {
        do {
          image.validate(gc);
          Graphics2D g=image.createGraphics();
          g.setRenderingHint(RenderingHints.KEY_ANTIALIASING,RenderingHints.VALUE_ANTIALIAS_ON);
          g.setColor(Color.WHITE); g.fillRect(0,0,1600,1000); g.setFont(font);
          for(int row=0;row<35;row++) {
            g.setColor(row%2==0?new Color(240,244,249):Color.WHITE); g.fillRect(0,row*28,1600,28);
            g.setColor(Color.DARK_GRAY); g.drawString("GET /example    200    text/html    "+row,12,row*28+22);
          }
          g.setColor(new Color(20,100,200,100)); g.fillRoundRect(frame*5,100,300,300,20,20); g.dispose();
        } while(image.contentsLost());
        Toolkit.getDefaultToolkit().sync();
      }
      // Force completion/readback at each pass boundary, on both drivers.
      BufferedImage completed=image.getSnapshot();
      if(completed.getRGB(1599,999)==0) throw new RuntimeException("Invalid readback");
      double wall=(System.nanoTime()-start)/1e6,used=(bean.getProcessCpuTime()-cpu)/1e6;
      if(pass!=0) System.out.print(",");
      System.out.printf(java.util.Locale.ROOT,"{\"wall_ms\":%.4f,\"cpu_ms\":%.4f,\"warmup\":%s}",wall,used,pass==0);
    }
    System.out.println("]}"); image.flush();
  }
}
